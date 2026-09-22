package com.benchmark.library;

import java.time.LocalDate;

public class Loan {

    private final Book book;
    private final Member member;
    private final LocalDate borrowedOn;
    private LocalDate returnedOn;

    public Loan(Book book, Member member) {
        this.book = book;
        this.member = member;
        this.borrowedOn = LocalDate.now();
    }

    public Book getBook() {
        return book;
    }

    public Member getMember() {
        return member;
    }

    public LocalDate getBorrowedOn() {
        return borrowedOn;
    }

    public LocalDate getReturnedOn() {
        return returnedOn;
    }

    public boolean isReturned() {
        return returnedOn != null;
    }

    public void markReturned() {
        returnedOn = LocalDate.now();
    }
}