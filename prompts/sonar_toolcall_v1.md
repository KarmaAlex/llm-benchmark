Your task is to modify the provided source code so that the specified SonarQube issue is resolved.

## SonarQube Rule

{{rule}}

## Issue

{{issue}}

## Project Resources

The following are the files available in the project. Use their contents to understand the existing implementation and determine the appropriate changes.

Each line is preceded by the line number in the original file, purely so you can locate code while reading. A line containing `<BLANK>` represents an empty line in the original source file. Never reference line numbers or the `<BLANK>` token in a tool call argument — always use the real source text.

{{files}}

## Instructions

1. Identify the exact code construct that violates the specified SonarQube rule.

2. Use the reported file and line number as the primary location of the issue. Inspect the surrounding code when necessary to understand the violation and determine the correct fix.

3. Make the minimal necessary change required to resolve the issue, preserving existing behavior otherwise, and without modifying unrelated code.

4. Call the `edit_file` tool once for every change you need to make. Call it multiple times if the fix requires edits to more than one location or more than one file.

Do not output any text, explanation, or diff syntax. Express every change exclusively through `edit_file` tool calls.
