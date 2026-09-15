# SecurePass — Cryptographically Secure Random Password Generator

> **Internship Submission**: Task 3 — Random Password Generator  
> **Author**: Avinash Pillalamarri  
> **Tech Stack**: HTML5, CSS3, JavaScript (ES6+), Web Crypto API, Clipboard API

---

## 🔒 Project Overview

**SecurePass** is a production-quality, privacy-first web application designed to generate strong, cryptographically secure passwords directly inside the browser. It gives users fine-grained control over password length and character distributions while enforcing strict security rules and zero server/database tracking.

---

## ✨ Key Features

- **Cryptographically Secure Randomness**: Uses `window.crypto.getRandomValues()` with rejection sampling to eliminate modulo bias. Standard pseudo-random `Math.random()` is **never** used.
- **Guaranteed Character Inclusion**: Ensures that generated passwords contain **at least one character from every active character type** (Uppercase, Lowercase, Numbers, Symbols).
- **Ambiguous Character Filtering**: Optional exclusion of easily confused characters (`0`, `O`, `o`, `1`, `l`, `I`).
- **Synchronized Length Controls**: Dual range slider and numerical spinbox input ($8 \le \text{length} \le 64$, default $16$).
- **Strict Validation Rules**: Requires a minimum of 2 active character types and enforces length boundaries ($8$ to $64$).
- **Dynamic Strength Estimation**: Live password strength gauge (`Weak`, `Medium`, `Strong`) evaluating length, character set count, and entropy bits.
- **Clipboard Integration**: One-click copy with visual feedback (`✓ Copied!`) and automatic copy attempt on generation.
- **Session-Only History**: Stores up to the **5 most recent passwords** in volatile JS memory. Features password masking toggles and individual copy actions. Wiped instantly on page refresh.
- **Modern Cybersecurity Interface**: Dark navy/charcoal UI theme with high accessibility contrast, responsive layouts for desktop, tablet, and mobile, and keyboard navigation support.
- **One-Click Reset**: Resets all configuration choices to default standards and generates a fresh password.

---

## 🛡️ Security Rationale

### Why Web Crypto API over `Math.random()`?
Standard JavaScript `Math.random()` relies on Pseudo-Random Number Generators (PRNGs) like V8's xorshift128+. PRNGs are deterministic algorithm outputs initialized by a seed value, making their output sequence predictable if an attacker observes a small window of generated numbers.

**SecurePass** exclusively uses `crypto.getRandomValues()`, which interfaces with the operating system's Cryptographically Secure Pseudo-Random Number Generator (CSPRNG) powered by hardware entropy sources (system interrupts, thermal noise, CPU timing). Rejection sampling is additionally applied to ensure perfect uniform distribution across candidate character set lengths.

### Privacy & Data Handling
- **Zero Server Communication**: 100% client-side code execution. No analytics, tracking pixels, or external API endpoints.
- **Zero Storage Persistence**: Passwords are never written to `localStorage`, `sessionStorage`, `cookies`, or IndexedDB.

---

## 📁 Project Structure

```text
securepass/
│
├── index.html          # Semantic HTML5 document structure
├── style.css           # Cybersecurity dark theme & responsive styles
├── script.js           # Core CSPRNG generator, entropy logic, and UI bindings
│
├── assets/
│   └── favicon.svg     # SVG shield & lock brand icon
│
└── README.md           # Project documentation and submission details
```

---

## 🚀 How to Run

1. **Direct Browser Execution**:
   Simply open `index.html` in modern browsers (Chrome, Firefox, Edge, Safari, Brave).

2. **Local Web Server (Recommended for Clipboard API)**:
   For optimal Clipboard API support across all browsers, serve the folder over `localhost` or HTTPS:
   ```bash
   # Using Python 3 built-in HTTP server
   cd securepass
   python -m http.server 8000
   ```
   Then open `http://localhost:8000` in your web browser.

---

## 🧪 Verification & Testing

The project has been tested against the following test matrix:

- [x] **Length Boundaries**: Length < 8 or > 64 rejected with explicit warning message.
- [x] **Type Validation**: Blocked generation when < 2 character types are selected.
- [x] **Guaranteed Types**: Verified present in 1,000+ iteration test passes.
- [x] **Ambiguous Exclusion**: Confirmed total absence of `0, O, o, 1, l, I` when checked.
- [x] **History Memory**: Verified max 5 entries, newest first, and total erasure upon browser refresh.
- [x] **Responsiveness**: Checked UI usability on mobile (<640px), tablet, and desktop viewports.
