/*
script.js
---------
Client-side interactivity:
1. Dynamic question builder for Create Exam form with full validation.
2. Verification button on Blockchain page with instant JSON response.
3. Form validation helpers and double-submission protection.
*/

let questionCount = 0;

function updateQuestionBadge() {
    const badge = document.getElementById("question-count-badge");
    const container = document.getElementById("questions");
    if (badge && container) {
        const count = container.querySelectorAll(".question-block").length;
        badge.textContent = `${count} Question${count === 1 ? '' : 's'}`;
    }
}

function reindexQuestions() {
    const container = document.getElementById("questions");
    if (!container) return;
    const blocks = container.querySelectorAll(".question-block");
    blocks.forEach((block, idx) => {
        block.id = `q-block-${idx}`;
        const titleStrong = block.querySelector("strong");
        if (titleStrong) {
            titleStrong.textContent = `Question ${idx + 1}`;
        }
        const removeBtn = block.querySelector("button.btn-remove-q") || block.querySelector("button[onclick*='removeQuestion']");
        if (removeBtn) {
            removeBtn.setAttribute("onclick", `removeQuestion(${idx})`);
        }
        const radioInputs = block.querySelectorAll('input[type="radio"]');
        radioInputs.forEach((r, j) => {
            r.name = `correct_${idx}`;
            r.id = `q_${idx}_opt_${j}`;
            const label = block.querySelector(`label[for="${r.id}"]`) || r.nextElementSibling;
            if (label && label.tagName === "LABEL") {
                label.htmlFor = `q_${idx}_opt_${j}`;
            }
        });
        const optInputs = block.querySelectorAll('input[type="text"]:not([name="question_text"])');
        optInputs.forEach((opt, j) => {
            opt.name = `option_${idx}_${j}`;
        });
    });
    questionCount = blocks.length;
    updateQuestionBadge();
}

function removeQuestion(idx) {
    const block = document.getElementById(`q-block-${idx}`);
    if (block) {
        block.remove();
        reindexQuestions();
    }
}

function addQuestion() {
    const container = document.getElementById("questions");
    if (!container) return;

    const i = questionCount++;
    const div = document.createElement("div");
    div.className = "question-block";
    div.id = `q-block-${i}`;
    div.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <strong style="color: var(--accent);">Question ${container.children.length + 1}</strong>
            <button type="button" class="btn btn-secondary btn-sm btn-remove-q" onclick="removeQuestion(${i})" style="padding: 2px 8px; font-size: 0.78rem; color: var(--danger);">&times; Remove</button>
        </div>
        <div style="margin-bottom: 12px;">
            <input type="text" name="question_text" required placeholder="Enter question statement" style="font-weight: 500; margin-bottom: 6px;">
        </div>
        <label style="margin-bottom: 6px; font-size: 0.85rem;">Answer Options (mark the radio button for the correct option):</label>
        ${['A', 'B', 'C', 'D'].map((label, j) => `
            <div class="option-row">
                <input type="radio" name="correct_${i}" value="${j}" ${j === 0 ? "checked" : ""} id="q_${i}_opt_${j}" title="Mark Option ${label} as correct">
                <label for="q_${i}_opt_${j}" style="font-weight: 600; min-width: 22px; color: var(--muted); margin: 0; cursor: pointer;">${label}.</label>
                <input type="text" name="option_${i}_${j}" required placeholder="Option ${label} text">
            </div>
        `).join("")}
    `;
    container.appendChild(div);
    reindexQuestions();
}

document.addEventListener("DOMContentLoaded", () => {
    // Admin Create & Edit Exam handlers
    const addBtn = document.getElementById("add-question-btn");
    const examForm = document.getElementById("create-exam-form") || document.getElementById("edit-exam-form");

    if (addBtn && examForm) {
        addBtn.addEventListener("click", addQuestion);

        const existingBlocks = document.querySelectorAll(".question-block");
        if (existingBlocks.length === 0) {
            addQuestion();
        } else {
            questionCount = existingBlocks.length;
            updateQuestionBadge();
        }

        examForm.addEventListener("submit", (e) => {
            const startInput = document.getElementById("start_time");
            const endInput = document.getElementById("end_time");
            const durInput = document.getElementById("duration");

            if (startInput && endInput) {
                const startTime = new Date(startInput.value);
                const endTime = new Date(endInput.value);
                if (endTime <= startTime) {
                    alert("Validation Error: Exam End Time must be strictly after Start Time.");
                    endInput.focus();
                    e.preventDefault();
                    return;
                }
            }

            if (durInput && parseInt(durInput.value) <= 0) {
                alert("Validation Error: Exam duration must be a positive integer.");
                durInput.focus();
                e.preventDefault();
                return;
            }

            const qBlocks = document.querySelectorAll(".question-block");
            if (qBlocks.length === 0) {
                alert("Validation Error: Please add at least one question to the exam.");
                e.preventDefault();
                return;
            }
        });
    }

    // Blockchain page instant verification
    const verifyBtn = document.getElementById("verify-btn");
    if (verifyBtn) {
        verifyBtn.addEventListener("click", async () => {
            const resultBox = document.getElementById("verify-result");
            resultBox.innerHTML = '<span class="status-badge status-upcoming">Cryptographic Verification in Progress...</span>';

            try {
                const response = await fetch("/verify", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" }
                });
                const data = await response.json();

                if (data.valid) {
                    resultBox.innerHTML = `
                        <div class="status-badge status-valid" style="font-size:1rem; padding:8px 18px;">
                            &#10003; VALID - No Tampering Detected
                        </div>
                        <p style="color: var(--muted); margin-top:8px; font-size:0.9rem;">
                            Every block's stored SHA-256 hash matches its recomputed hash, and all cryptographic hash links are intact.
                        </p>`;
                } else {
                    const problemsHtml = data.problems.map(p => `<li>${p}</li>`).join("");
                    resultBox.innerHTML = `
                        <div class="status-badge status-invalid" style="font-size:1rem; padding:8px 18px;">
                            &#9888; TAMPERING DETECTED
                        </div>
                        <p style="color: var(--danger); font-size:0.9rem; margin-top:6px;">
                            Unauthorized modification detected because the stored cryptographic hash no longer matches.
                        </p>
                        <ul style="color: var(--danger); margin-top:10px; text-align:left; display:inline-block;">${problemsHtml}</ul>`;
                }

                // Refresh after demo observation
                setTimeout(() => window.location.reload(), 2500);
            } catch (err) {
                resultBox.innerHTML = `<p style="color: var(--danger);">Error checking blockchain: ${err}</p>`;
            }
        });
    }

    // Student Exam Countdown Timer & Auto-Submission Engine
    const timerContainer = document.getElementById("exam-timer-container");
    const timerDisplay = document.getElementById("exam-timer-display");
    const studentExamForm = document.getElementById("student-exam-form");

    let isSubmitting = false;

    function formatTime(totalSeconds) {
        if (totalSeconds <= 0) return "00:00";
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        const pad = (n) => String(n).padStart(2, "0");
        if (hours > 0) {
            return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
        }
        return `${pad(minutes)}:${pad(seconds)}`;
    }

    function updateTimerClass(container, remainingSeconds) {
        container.classList.remove("timer-normal", "timer-warning", "timer-critical");
        if (remainingSeconds <= 60) {
            container.classList.add("timer-critical");
        } else if (remainingSeconds <= 300) {
            container.classList.add("timer-warning");
        } else {
            container.classList.add("timer-normal");
        }
    }

    function autoSubmitExam() {
        if (isSubmitting || !studentExamForm) return;
        isSubmitting = true;

        const autoInput = document.getElementById("auto_submit");
        if (autoInput) autoInput.value = "true";

        const submitBtn = document.getElementById("exam-submit-btn");
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerText = "Time Expired. Submitting...";
            submitBtn.style.opacity = "0.7";
        }

        // Bypass browser HTML5 required validation for automatic timeout submission
        studentExamForm.noValidate = true;
        studentExamForm.submit();
    }

    if (timerContainer && timerDisplay) {
        const rawSeconds = parseInt(timerContainer.getAttribute("data-remaining-seconds"), 10);
        const initialRemaining = isNaN(rawSeconds) ? 0 : rawSeconds;
        const startTime = Date.now();

        // Initial render
        timerDisplay.textContent = formatTime(initialRemaining);
        updateTimerClass(timerContainer, initialRemaining);

        if (initialRemaining <= 0) {
            autoSubmitExam();
        } else {
            const timerInterval = setInterval(() => {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                const currentRemaining = Math.max(0, initialRemaining - elapsed);

                timerDisplay.textContent = formatTime(currentRemaining);
                updateTimerClass(timerContainer, currentRemaining);

                if (currentRemaining <= 0) {
                    clearInterval(timerInterval);
                    timerDisplay.textContent = "00:00 (Expired)";
                    autoSubmitExam();
                }
            }, 1000);
        }
    }

    // Student Exam submission double-click prevention
    if (studentExamForm) {
        studentExamForm.addEventListener("submit", (e) => {
            if (isSubmitting) {
                e.preventDefault();
                return;
            }
            isSubmitting = true;
            const submitBtn = document.getElementById("exam-submit-btn");
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerText = "Submitting & Sealing on Blockchain...";
                submitBtn.style.opacity = "0.7";
            }
        });
    }
});
