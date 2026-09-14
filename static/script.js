/*
script.js
---------
Two small pieces of interactivity, kept deliberately simple:

1. On the home page: lets the admin click "+ Add Question" to add
   more MCQ fields to the create-exam form without reloading the page.

2. On the blockchain page: lets the "Verify Blockchain" button re-check
   the chain via a fetch() call to POST /verify, and update the status
   banner on the page immediately with the JSON response -- no page
   reload needed, which makes the tampering demo feel instant.
*/

let questionCount = 0;

function addQuestion() {
    const container = document.getElementById("questions");
    if (!container) return;

    const i = questionCount++;
    const div = document.createElement("div");
    div.className = "question-block";
    div.innerHTML = `
        <label>Question ${i + 1}</label>
        <input type="text" name="question_text" required placeholder="Enter question text">
        ${[0, 1, 2, 3].map(j => `
            <div class="option-row">
                <input type="radio" name="correct_${i}" value="${j}" ${j === 0 ? "checked" : ""} title="Mark as correct answer">
                <input type="text" name="option_${i}_${j}" required placeholder="Option ${j + 1}">
            </div>
        `).join("")}
        <p style="color: var(--muted); font-size: 0.78rem;">Select the radio button next to the correct option.</p>
    `;
    container.appendChild(div);
}

document.addEventListener("DOMContentLoaded", () => {
    const addBtn = document.getElementById("add-question-btn");
    if (addBtn) {
        addBtn.addEventListener("click", addQuestion);
        // Start every new exam form with one question visible.
        addQuestion();
    }

    const verifyBtn = document.getElementById("verify-btn");
    if (verifyBtn) {
        verifyBtn.addEventListener("click", async () => {
            const resultBox = document.getElementById("verify-result");
            resultBox.innerHTML = "Checking chain...";

            try {
                const response = await fetch("/verify", { method: "POST" });
                const data = await response.json();

                if (data.valid) {
                    resultBox.innerHTML = `
                        <div class="status-badge status-valid" style="font-size:1rem; padding:8px 18px;">
                            VALID - No tampering detected
                        </div>
                        <p style="color: var(--muted); margin-top:8px;">
                            Every block's stored hash matches its recomputed hash, and every
                            previous_hash link is intact.
                        </p>`;
                } else {
                    const problemsHtml = data.problems.map(p => `<li>${p}</li>`).join("");
                    resultBox.innerHTML = `
                        <div class="status-badge status-invalid" style="font-size:1rem; padding:8px 18px;">
                            TAMPERING DETECTED
                        </div>
                        <ul style="color: var(--danger); margin-top:10px;">${problemsHtml}</ul>`;
                }

                // Also refresh each block card's visual mismatch state
                // by simply reloading the block list section, which is
                // simplest and keeps this demo easy to follow.
                setTimeout(() => window.location.reload(), 1800);
            } catch (err) {
                resultBox.innerHTML = `<p style="color: var(--danger);">Error checking chain: ${err}</p>`;
            }
        });
    }
});
