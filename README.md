# Blockchain-Based Secure Online Examination System

A full-stack web-based examination system designed to demonstrate how **blockchain-style hash linking can be used to provide tamper-evident examination results**.

The system provides separate teacher and student workflows, scheduled examinations, secure authentication, automatic grading, one-attempt enforcement, and blockchain-based integrity verification.

> **Important:** This project implements a blockchain/hash-chain from scratch in Python using SHA-256. It does **not** use Ethereum, Solidity, smart contracts, cryptocurrency, or an external blockchain network. It is a private, single-server educational implementation focused on understanding blockchain principles.

## Live Demo

**Live Application:**
https://deore123.pythonanywhere.com/

The application is deployed on **PythonAnywhere** and uses SQLite for persistent storage.

---

## Features

### Teacher

* Secure teacher login
* Create multiple-choice examinations
* Configure exam start and end times
* Add multiple-choice questions with four options
* Define correct answers
* View submitted student results
* View blockchain records
* Verify blockchain integrity

### Student

* Student self-registration
* Full name, username, roll number/PRN and password
* Login using **username or roll number**
* View currently available examinations
* Take an examination only during its scheduled time window
* Submit an examination once
* Receive automatic score calculation
* View detailed answer breakdown
* View the blockchain block associated with the result

### Blockchain Integrity

Every submitted examination result is sealed into a block containing informa
