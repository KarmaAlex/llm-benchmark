package com.benchmark.library;

public class LibraryService {

    private static final int MAX_ACTIVE_LOANS = 5;

    private final Library library;

    public LibraryService(Library library) {
        this.library = library;
    }

    public boolean borrowBook(int memberId, String isbn) {
        Member member = library.findMember(memberId);
        Book book = library.findBook(isbn);

        if (member == null || book == null) {
            return false;
        }
        
        if (member.isActive() == true && book.isAvailable()) {
            if (member.getOutstandingLoans() >= MAX_ACTIVE_LOANS) {
                return false;
            }

            Loan loan = new Loan(book, member);

            book.setAvailable(false);
            member.addLoan();
            library.addLoan(loan);

            return true;
        }

        return false;
    }

    public boolean returnBook(int memberId, String isbn) {
        for (Loan loan : library.getLoans()) {
            if (loan.getMember().getId() == memberId
                    && loan.getBook().getIsbn().equals(isbn)
                    && !loan.isReturned()) {

                loan.markReturned();
                loan.getBook().setAvailable(true);
                loan.getMember().removeLoan();

                return true;
            }
        }

        return false;
    }

    public int countAvailableBooks() {
        int count = 0;

        for (Book book : library.getBooks()) {
            if (book.isAvailable()) {
                count++;
            }
        }

        return count;
    }
}