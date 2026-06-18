import re
from dataclasses import dataclass
from pathlib import Path
import chardet


@dataclass
class ApplyResult:
    """
    Honest report of what apply() actually did for one patch instruction.

    success=False means the file was NOT modified — main.py and
    PatchQualityChecker must treat this as a hard failure, not infer
    success/failure by re-reading file state afterward (that approach
    produced false positives, since unrelated existing text in the file
    could satisfy a naive "is the new content present" check even when
    nothing was actually changed).
    """
    file: str
    action: str
    success: bool
    reason: str = ""   # empty string when success=True


def _detect_line_ending(text):
    """
    Determine the dominant line-ending style already used in a file's
    text, so we can write the WHOLE file back out consistently — never
    leaving some lines as \\r\\n and others as \\n.

    This is the fix for: GitHub's diff view showing every line as
    changed after a patch, when in reality only 1-2 lines had real
    content changes. The cause was mixed line endings within a single
    file (original lines kept \\r\\n, but spliced-in patch content used
    plain \\n) — GitHub's renderer treats a file with inconsistent line
    endings as fully changed even though git's actual diff only flags
    the real content change.
    """
    crlf_count = text.count("\r\n")
    # Count bare LF (not part of a CRLF pair)
    lf_count = text.count("\n") - crlf_count

    if crlf_count == 0 and lf_count == 0:
        # Single-line file or empty file — default to LF (POSIX/git standard)
        return "\n"

    return "\r\n" if crlf_count >= lf_count else "\n"


def _normalize_to_lf(text):
    """Convert all line endings in text to plain \\n for internal processing."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _apply_line_ending(text, line_ending):
    """
    Convert a \\n-normalized string to use the given line_ending
    consistently throughout. Used as the final step before writing,
    so the entire file — original content AND newly spliced-in patch
    content — ends up with one consistent line-ending style.
    """
    if line_ending == "\n":
        return text
    return text.replace("\n", line_ending)


def _normalize_whitespace(text):
    """
    Collapse all runs of whitespace (spaces, tabs) to a single space,
    and strip leading/trailing whitespace from each line, WITHOUT
    merging separate lines together. Used as a fallback match when an
    exact substring match fails — LLM-generated `target` strings often
    differ from the real file only in indentation width or trailing
    spaces, not in actual content.
    """
    lines = text.split("\n")
    normalized_lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in lines
    ]
    return "\n".join(normalized_lines)


def _find_with_fallback(haystack, needle):
    """
    Try an exact substring match first. If that fails, try again with
    both sides whitespace-normalized, and if THAT matches, return the
    exact-text span in the original haystack that corresponds to it.

    Returns the exact substring of `haystack` to replace, or None if
    no match was found even after normalization.

    NOTE: caller is expected to pass in \\n-normalized haystack/needle
    (see PatchApplier._read_file), so this function never needs to
    reason about \\r\\n at all — line-ending consistency is handled
    once, centrally, at read/write time instead.
    """
    if needle in haystack:
        return needle

    needle_norm = _normalize_whitespace(needle)
    haystack_lines = haystack.split("\n")
    needle_line_count = needle_norm.count("\n") + 1

    for i in range(len(haystack_lines) - needle_line_count + 1):
        window = haystack_lines[i:i + needle_line_count]
        window_norm = _normalize_whitespace("\n".join(window))

        if window_norm == needle_norm:
            return "\n".join(window)

    return None


class PatchApplier:

    def resolve_file_path(self, repo_path, file_name):
        repo_path = Path(repo_path)
        matches = list(repo_path.rglob(file_name))
        if matches:
            return matches[0]
        return repo_path / file_name

    # ------------------------------------------------------------------
    # Encoding helpers
    # ------------------------------------------------------------------

    def detect_encoding(self, file_path):
        raw = Path(file_path).read_bytes()

        if raw[:2] == b'\xff\xfe':
            return "utf-16-le"
        if raw[:2] == b'\xfe\xff':
            return "utf-16-be"
        if raw[:3] == b'\xef\xbb\xbf':
            return "utf-8-sig"

        result = chardet.detect(raw)
        encoding = result.get("encoding") or "utf-8"

        if encoding.lower() == "utf-16":
            encoding = "utf-16-le"

        return encoding

    def _read_file(self, file_path):
        """
        Read a file and return (text, encoding, line_ending).

        `text` is ALWAYS normalized to plain \\n internally, regardless
        of the file's actual line-ending style. This means every
        string operation in this class (substring search, replace,
        whitespace-fallback matching) only ever has to deal with \\n —
        all the \\r\\n-vs-\\n complexity is handled once here and once
        in _write_file, not scattered across every operation.

        The original line_ending is returned so _write_file can convert
        the WHOLE final result back to it consistently — this is what
        prevents the mixed-line-ending bug where patched lines used \\n
        while the rest of the file kept \\r\\n.
        """
        encoding = self.detect_encoding(file_path)
        raw_text = Path(file_path).read_bytes().decode(encoding)

        if raw_text.startswith('\ufeff'):
            raw_text = raw_text[1:]

        line_ending = _detect_line_ending(raw_text)
        text = _normalize_to_lf(raw_text)

        return text, encoding, line_ending

    def _write_file(self, file_path, text, encoding, line_ending):
        """
        Write text back to file using the original encoding AND the
        original line-ending style, applied consistently across the
        ENTIRE file content — not just the newly patched region.

        `text` is expected to be \\n-normalized internally (as produced
        by _read_file + string operations); this converts it back to
        `line_ending` as the very last step before writing bytes.
        """
        file_path = Path(file_path)
        enc_lower = encoding.lower()

        final_text = _apply_line_ending(text, line_ending)

        if enc_lower == "utf-16-le":
            file_path.write_bytes(b'\xff\xfe' + final_text.encode("utf-16-le"))
        elif enc_lower == "utf-16-be":
            file_path.write_bytes(b'\xfe\xff' + final_text.encode("utf-16-be"))
        else:
            # Write raw bytes (not write_text) to guarantee the exact
            # line-ending bytes we computed are what lands on disk —
            # write_text's newline-translation behavior varies by
            # platform and would undo this fix on Windows.
            file_path.write_bytes(final_text.encode(encoding))

    # ------------------------------------------------------------------
    # Public apply entry point
    # ------------------------------------------------------------------

    def apply(self, repo_path, patch_plan):
        """
        Apply every patch in patch_plan and return a list of ApplyResult,
        one per patch, in the same order. Callers (main.py,
        PatchQualityChecker) must check these results rather than
        assuming success.
        """
        results = []

        for patch in patch_plan.patches:

            target_file = self.resolve_file_path(repo_path, patch.file)

            if patch.action == "create":
                result = self.create_file(target_file, patch.content)
                results.append(result)
                continue

            if not target_file.exists():
                print(f"File not found: {target_file}")
                results.append(
                    ApplyResult(
                        file=patch.file,
                        action=patch.action,
                        success=False,
                        reason=f"File not found: {target_file}"
                    )
                )
                continue

            if patch.action == "append":
                result = self.append_content(target_file, patch.content)

            elif patch.action == "insert_after":
                result = self.insert_after(target_file, patch.target, patch.content)

            elif patch.action == "insert_before":
                result = self.insert_before(target_file, patch.target, patch.content)

            elif patch.action == "modify":
                result = self.modify(target_file, patch.target, patch.content)

            else:
                print(f"Unknown action '{patch.action}' for {patch.file} — skipped")
                result = ApplyResult(
                    file=patch.file,
                    action=patch.action,
                    success=False,
                    reason=f"Unknown action '{patch.action}'"
                )

            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Operations — each returns an ApplyResult
    # ------------------------------------------------------------------

    def append_content(self, file_path, content):
        text, encoding, line_ending = self._read_file(file_path)
        print(f"[PatchApplier] append_content | encoding={encoding} | file={file_path}")

        content = _normalize_to_lf(content)

        if not text.endswith("\n"):
            text += "\n"
        text += content + "\n"

        self._write_file(file_path, text, encoding, line_ending)
        print(f"Appended to {file_path}")

        return ApplyResult(
            file=str(file_path),
            action="append",
            success=True
        )

    def insert_after(self, file_path, target, content):
        text, encoding, line_ending = self._read_file(file_path)
        print(f"[PatchApplier] insert_after | encoding={encoding} | file={file_path}")

        target = _normalize_to_lf(target)
        content = _normalize_to_lf(content)

        match = _find_with_fallback(text, target)

        if match is None:
            reason = f"target not found (even after whitespace-normalized fallback match)"
            print(f"insert_after failed: {reason}")
            print(f"  target was: {target!r}")
            return ApplyResult(
                file=str(file_path),
                action="insert_after",
                success=False,
                reason=reason
            )

        replacement = match + "\n" + content
        text = text.replace(match, replacement, 1)

        self._write_file(file_path, text, encoding, line_ending)
        print(f"Updated {file_path}")

        return ApplyResult(
            file=str(file_path),
            action="insert_after",
            success=True
        )

    def insert_before(self, file_path, target, content):
        text, encoding, line_ending = self._read_file(file_path)
        print(f"[PatchApplier] insert_before | encoding={encoding} | file={file_path}")

        target = _normalize_to_lf(target)
        content = _normalize_to_lf(content)

        match = _find_with_fallback(text, target)

        if match is None:
            reason = f"target not found (even after whitespace-normalized fallback match)"
            print(f"insert_before failed: {reason}")
            print(f"  target was: {target!r}")
            return ApplyResult(
                file=str(file_path),
                action="insert_before",
                success=False,
                reason=reason
            )

        replacement = content + "\n" + match
        text = text.replace(match, replacement, 1)

        self._write_file(file_path, text, encoding, line_ending)
        print(f"Updated {file_path}")

        return ApplyResult(
            file=str(file_path),
            action="insert_before",
            success=True
        )

    def modify(self, file_path, target, content):
        """
        Replace the first occurrence of target with content.

        target  = exact (or near-exact) existing text to find
        content = new text that replaces it

        Tries an exact match first. If that fails, falls back to a
        whitespace-normalized match — LLM-generated targets frequently
        differ from the real file only in indentation/trailing spaces,
        which would otherwise cause a silent, undetected failure (the
        original bug: the file was left unchanged, but nothing
        downstream noticed).

        Preserves the file's original encoding. Returns ApplyResult —
        success=False means the file was NOT modified.
        """
        text, encoding, line_ending = self._read_file(file_path)
        print(f"[PatchApplier] modify | encoding={encoding} | file={file_path}")

        if not target:
            reason = "target is empty"
            print(f"modify rejected: {reason} for {file_path}")
            return ApplyResult(
                file=str(file_path),
                action="modify",
                success=False,
                reason=reason
            )

        target = _normalize_to_lf(target)
        content = _normalize_to_lf(content)

        match = _find_with_fallback(text, target)

        if match is None:
            reason = "target not found (even after whitespace-normalized fallback match)"
            print(f"modify failed: {reason}")
            print(f"  target was: {target!r}")
            return ApplyResult(
                file=str(file_path),
                action="modify",
                success=False,
                reason=reason
            )

        text = text.replace(match, content, 1)

        self._write_file(file_path, text, encoding, line_ending)
        print(f"Modified {file_path}")

        return ApplyResult(
            file=str(file_path),
            action="modify",
            success=True
        )

    def create_file(self, file_path, content):
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        print(f"Created {file_path}")

        return ApplyResult(
            file=str(file_path),
            action="create",
            success=True
        )