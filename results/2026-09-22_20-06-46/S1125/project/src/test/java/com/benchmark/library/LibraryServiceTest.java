package com.benchmark.library;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class LibraryServiceTest {

    private Library library;
    private LibraryService service;
    private Member member;
    private Book book;

    @BeforeEach
    void setUp() {
        library = new Library();

        member = new Member(1, "Alice");
        book = new Book("978-0134685991", "Effective Java", "Joshua Bloch");

        library.addMember(member);
        library.addBook(book);

        service = new LibraryService(library);
    }

    @Test
    void activeMemberCanBorrowAvailableBook() {
        assertTrue(service.borrowBook(member.getId(), book.getIsbn()));

        assertFalse(book.isAvailable());
        assertEquals(1, member.getOutstandingLoans());
        assertEquals(0, service.countAvailableBooks());
    }

    @Test
    void inactiveMemberCannotBorrowBook() {
        member.setActive(false);

        assertFalse(service.borrowBook(member.getId(), book.getIsbn()));

        assertTrue(book.isAvailable());
        assertEquals(0, member.getOutstandingLoans());
    }

    @Test
    void memberCannotBorrowUnavailableBook() {
        assertTrue(service.borrowBook(member.getId(), book.getIsbn()));

        Member secondMember = new Member(2, "Bob");
        library.addMember(secondMember);

        assertFalse(service.borrowBook(secondMember.getId(), book.getIsbn()));
        assertEquals(1, member.getOutstandingLoans());
        assertEquals(0, secondMember.getOutstandingLoans());
    }

    @Test
    void borrowedBookCanBeReturned() {
        assertTrue(service.borrowBook(member.getId(), book.getIsbn()));
        assertTrue(service.returnBook(member.getId(), book.getIsbn()));

        assertTrue(book.isAvailable());
        assertEquals(0, member.getOutstandingLoans());
        assertEquals(1, service.countAvailableBooks());
    }

    @Test
    void memberCannotExceedLoanLimit() {
        for (int i = 0; i < 5; i++) {
            Book additionalBook = new Book(
                    "978-000000000" + i,
                    "Book " + i,
                    "Author " + i
            );

            library.addBook(additionalBook);

            assertTrue(
                    service.borrowBook(member.getId(), additionalBook.getIsbn())
            );
        }

        Book extraBook = new Book(
                "978-9999999999",
                "Extra Book",
                "Another Author"
        );

        library.addBook(extraBook);

        assertFalse(
                service.borrowBook(member.getId(), extraBook.getIsbn())
        );

        assertEquals(5, member.getOutstandingLoans());
        assertTrue(extraBook.isAvailable());
    }
}