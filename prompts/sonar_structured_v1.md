Your task is to modify the provided source code so that the specified SonarQube issue is resolved.

## SonarQube Rule

{{rule}}

## Issue

{{issue}}

## Project Resources

The following are the files available in the project. Use their contents to understand the existing implementation and determine the appropriate changes.

Each line is preceded by the line number in the original file, purely so you can locate code while reading. Line-number prefixes are metadata and must never appear in your output. A line containing `<BLANK>` represents an empty line in the original source file.

{{files}}

## Instructions

1. Identify the exact code construct that violates the specified SonarQube rule.

2. Use the reported file and line number as the primary location of the issue. Inspect the surrounding code when necessary to understand the violation and determine the correct fix.

3. Modify the code so that the specific reported SonarQube issue is actually resolved.

4. Verify that the modified code no longer violates the specified SonarQube rule.

5. Make the minimal necessary change required to resolve the issue.

6. Preserve the existing functionality and behavior of the application unless a change is necessary to resolve the issue.

7. Do not modify unrelated code.

8. Ensure that the proposed changes are consistent with the existing project structure, coding style, and APIs.

9. Do not make a change merely to produce output. If the issue requires a code change, the change must affect the code responsible for the reported violation.

## How to describe the change

You do not compute a diff and you never reference line numbers in your output. Instead, describe each change as an edit: the exact original text to find (`search`), and what it should become (`replacement`). The harness locates `search` in the real file itself, so you never need to count lines or track offsets.

Return **only** a single fenced code block containing a JSON array of edit objects, in this exact shape:

```json
[
    {
        "path": "src/main/java/com/example/Foo.java",
        "search": "if (isValid == true) {",
        "replacement": "if (isValid) {"
    }
]
```

Rules for each edit object:

- `path`: the exact file path as shown in the project resources.
- `search`: the exact original source text to replace, copied from the file content above — **with real blank lines, not the `<BLANK>` token, and without any line-number prefix**. Include enough surrounding text to make the target unambiguous, but nothing more than necessary.
- `replacement`: the text that should replace `search`. Use real blank lines here too if any are needed.
- `occurrence` (optional, defaults to `1`): if `search` appears more than once in the file, which occurrence (1-indexed) to replace.

You may include multiple edit objects in the array, including edits to different files, or multiple edits to the same file. Every edit is applied independently.

Do not include any text outside the single fenced JSON array. Do not include explanations, diff syntax, or line-number prefixes anywhere in your output.
