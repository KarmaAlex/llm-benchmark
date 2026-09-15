Your task is to modify the provided source code so that the specified SonarQube issue is resolved.

## SonarQube Rule

{{rule}}

## Issue

{{issue}}

## Project Resources

The following are the files available in the project. Use their contents to understand the existing implementation and determine the appropriate changes.
Each line is preceded by the line number in the original file, they are not part of the code so do not include them in the patches.

{{files}}

The project resources above contain the exact contents of the source files. Preserve whitespace and blank lines when constructing the patch.

## Instructions

1. Analyze the SonarQube rule and the reported issue.
2. Inspect the provided project files to identify the code responsible for the issue.
3. Make the **minimal necessary changes** required to resolve the reported SonarQube issue.
4. Preserve the existing functionality and behavior of the application unless a change is necessary to resolve the issue.
5. Do not modify unrelated code.
6. Ensure that the proposed changes are consistent with the existing project structure, coding style, and APIs.
7. Return the changes as a **unified diff patch** that can be applied directly to the original project.
9. Do not include changes that are unnecessary for resolving the reported issue.

## Output Requirements

Your entire response must consist **only of the unified diff patch**.

Do not include:

* Explanations
* Descriptions of the changes
* Markdown code fences
* Comments outside the patch
* Any text before or after the patch

If no changes are necessary, return an empty response.
