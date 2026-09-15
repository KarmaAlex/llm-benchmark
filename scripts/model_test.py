"""
Simple llama.cpp benchmark utility.

Example:
    python test_llama.py ^
        --model models/qwen2.5-coder-3b-instruct-q4_k_m.gguf
"""

import argparse
import json
import time
from pathlib import Path

from llama_cpp import Llama


DEFAULT_PROMPT = """You are a helpful software engineer.

What follows is the content of a Java source file. Each line is preceded by its line number in the source file.

```Java
1 | package com.benchmark.library;   
2 |    <BLANK>
3 | public class LibraryService {   
4 |    <BLANK>
5 |     private static final int MAX_ACTIVE_LOANS = 5;   
6 |    <BLANK>
7 |     private final Library library;   
8 |    <BLANK>
9 |     public LibraryService(Library library) {  
10 |         this.library = library;  
11 |     }  
12 |   <BLANK>
13 |     public boolean borrowBook(int memberId, String isbn) {  
14 |         Member member = library.findMember(memberId);  
15 |         Book book = library.findBook(isbn);  
16 |   <BLANK>
17 |         if (member == null || book == null) {  
18 |             return false;  
19 |         }  
20 |   <BLANK>
21 |         if (member.isActive() == true && book.isAvailable()) {  
22 |             if (member.getOutstandingLoans() >= MAX_ACTIVE_LOANS) {  
23 |                 return false;  
24 |             }  
25 |   <BLANK>
26 |             Loan loan = new Loan(book, member);  
27 |   <BLANK>
28 |             book.setAvailable(false);  
29 |             member.addLoan();  
30 |             library.addLoan(loan);  
31 |   <BLANK>
32 |             return true;  
33 |         }  
34 |   <BLANK>
35 |         return false;  
36 |     }  
37 |   <BLANK>
38 |     public boolean returnBook(int memberId, String isbn) {  
39 |         for (Loan loan : library.getLoans()) {  
40 |             if (loan.getMember().getId() == memberId  
41 |                     && loan.getBook().getIsbn().equals(isbn)  
42 |                     && !loan.isReturned()) {  
43 |   <BLANK>
44 |                 loan.markReturned();  
45 |                 loan.getBook().setAvailable(true);  
46 |                 loan.getMember().removeLoan();  
47 |   <BLANK>
48 |                 return true;  
49 |             }  
50 |         }  
51 |   <BLANK>
52 |         return false;  
53 |     }  
54 |   <BLANK>
55 |     public int countAvailableBooks() {  
56 |         int count = 0;  
57 |   <BLANK>
58 |         for (Book book : library.getBooks()) {  
59 |             if (book.isAvailable()) {  
60 |                 count++;  
61 |             }  
62 |         }  
63 |   <BLANK>
64 |         return count;  
65 |     }  
66 | }
```

The format is:
<line number> | <source code>

A line containing `<BLANK>` represents an empty line in the original
source file.

The line number and `|` separator are annotations only and must NOT
appear in the generated output.

Do not include `<BLANK>` tokens in the output.

Can you tell me the contents of lines 18 to 24 of the code?
"""


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        required=True,
        help="Path to GGUF model"
    )

    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt to send"
    )

    parser.add_argument(
        "--ctx-size",
        type=int,
        default=8192,
    )

    parser.add_argument(
        "--gpu-layers",
        type=int,
        default=-1,
        help="-1 = offload as many layers as possible"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256
    )

    args = parser.parse_args()

    model_path = Path(args.model)

    if not model_path.exists():
        raise FileNotFoundError(model_path)

    print("=" * 70)
    print("Loading model...")
    print("=" * 70)

    load_start = time.perf_counter()

    llm = Llama(
        model_path=str(model_path),
        n_ctx=args.ctx_size,
        n_gpu_layers=args.gpu_layers,
        verbose=False,
    )

    load_time = time.perf_counter() - load_start

    print(f"Loaded in {load_time:.2f}s\n")

    print("=" * 70)
    print("Generating...")
    print("=" * 70)

    start = time.perf_counter()

    response = llm.create_chat_completion(
        messages=[
            {
                "role": "user",
                "content": args.prompt,
            }
        ],
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    elapsed = time.perf_counter() - start

    message = response["choices"][0]["message"]["content"]

    usage = response.get("usage", {})

    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    print("\n")
    print("=" * 70)
    print("MODEL RESPONSE")
    print("=" * 70)
    print(message)

    print("\n")
    print("=" * 70)
    print("STATISTICS")
    print("=" * 70)

    print(f"Load time          : {load_time:.2f}s")
    print(f"Inference time     : {elapsed:.2f}s")
    print(f"Prompt tokens      : {prompt_tokens}")
    print(f"Completion tokens  : {completion_tokens}")
    print(f"Total tokens       : {total_tokens}")

    if elapsed > 0:
        print(f"Tokens/sec         : {completion_tokens / elapsed:.2f}")

    Path("response.json").write_text(
        json.dumps(response, indent=2),
        encoding="utf-8",
    )

    print("\nSaved raw response to response.json")


if __name__ == "__main__":
    main()