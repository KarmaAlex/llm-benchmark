Your task is to modify the provided source code so that the specified SonarQube issue is resolved.

## SonarQube Rule

{{rule}}

## Issue

{{issue}}

## Project Resources

The following are the files available in the project. Use their contents to understand the existing implementation and determine the appropriate changes.

Each line is preceded by the line number in the original file. Line-number prefixes are metadata and are not part of the source code. Do not include them in the patch.

{{files}}

A line containing `<BLANK>` represents an empty line in the original source file.

## Instructions

1. Identify the exact code construct that violates the specified SonarQube rule.

2. Use the reported file and line number as the primary location of the issue. Inspect the surrounding code when necessary to understand the violation and determine the correct fix.

3. Modify the code so that the specific reported SonarQube issue is actually resolved.

4. Verify that the modified code no longer violates the specified SonarQube rule.

5. Make the minimal necessary change required to resolve the issue.

6. Preserve the existing functionality and behavior of the application unless a change is necessary to resolve the issue.

7. Do not modify unrelated code.

8. Ensure that the proposed changes are consistent with the existing project structure, coding style, and APIs.

9. Do not make a change merely to produce a diff. If the issue requires a code change, the change must affect the code responsible for the reported violation.

10. Do not return a no-op patch. The removed and added versions of a changed line must not be identical.

## Output Requirements

Your entire response must consist only of the unified diff patch.

The diff must:

- use `--- a/<path>` and `+++ b/<path>` headers;
- use valid `@@` hunk headers;
- use the exact file paths shown in the project resources;
- contain only changes necessary to resolve the reported issue;
- not include line-number prefixes;
- not include Markdown code fences;
- not include explanations;
- actually resolve the reported SonarQube issue.
- include only the modified lines and any necessary context
- be aligned with the source code exactly, including blank lines

Before returning the patch, internally verify that applying it to the provided source code removes the reported violation.

If no code change is necessary, return an empty response.