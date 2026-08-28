// HireUp — small optional enhancements in plain JavaScript (no frameworks,
// no external services). The site works fully without this file.
//
//  1. "Searching…" feedback on the homepage search button.
//  2. Voice input for the Profession and Location fields (Web Speech API).
//  3. "Read results aloud" on the results page (SpeechSynthesis API).
//
// Features 2 and 3 fall back gracefully when the browser lacks the API.

(function () {
    "use strict";

    enhanceSearchButton();
    enableVoiceInput();
    enableReadAloud();

    // ----- 1. "Searching…" button state ----------------------------------

    function enhanceSearchButton() {
        var form = document.querySelector(".search-card");
        if (!form) {
            return;
        }

        var button = form.querySelector(".btn-search");
        if (!button) {
            return;
        }
        var originalLabel = button.textContent; // keeps the current language

        form.addEventListener("submit", function () {
            button.textContent = originalLabel + "…";
            button.disabled = true;
        });

        // Reset if the user returns via the browser Back button (the page can
        // be restored from cache with the old label).
        window.addEventListener("pageshow", function () {
            button.textContent = originalLabel;
            button.disabled = false;
        });
    }

    // ----- 2. Voice input -----------------------------------------------

    function enableVoiceInput() {
        var micButtons = document.querySelectorAll(".btn-mic");
        var status = document.querySelector(".voice-status");
        if (!micButtons.length) {
            return; // not on the homepage
        }

        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        // Graceful fallback: no Web Speech API in this browser.
        if (!SpeechRecognition) {
            setStatus("Voice input isn't supported in this browser — please type instead.");
            return; // mic buttons stay hidden; typing/selecting still works
        }

        function setStatus(message) {
            if (status) {
                status.textContent = message || "";
            }
        }

        // Pick the dropdown option that best matches what the user said.
        function matchProfession(select, transcript) {
            var said = transcript.toLowerCase();
            var options = select.options;
            var i;

            for (i = 0; i < options.length; i++) {
                var label = options[i].value.toLowerCase();
                if (said.indexOf(label) !== -1 || label.indexOf(said) !== -1) {
                    return options[i];
                }
            }

            for (i = 0; i < options.length; i++) {
                var words = options[i].value.toLowerCase().split(/[^a-z]+/);
                for (var w = 0; w < words.length; w++) {
                    if (words[w].length >= 3 && said.indexOf(words[w]) !== -1) {
                        return options[i];
                    }
                }
            }

            return null;
        }

        function applyResult(button, transcript) {
            var target = document.getElementById(button.getAttribute("data-target"));
            if (!target) {
                return;
            }

            if (target.tagName === "SELECT") {
                var option = matchProfession(target, transcript);
                if (option) {
                    target.value = option.value;
                    setStatus('Profession set to "' + option.value + '".');
                } else {
                    setStatus('Didn’t match a profession for "' + transcript + '".');
                }
            } else {
                target.value = transcript.replace(/[.\s]+$/, "");
                setStatus('Location set to "' + target.value + '".');
            }
        }

        var activeRecognition = null;

        function startListening(button) {
            if (activeRecognition) {
                activeRecognition.stop();
                return;
            }

            var recognition = new SpeechRecognition();
            recognition.lang = "en-IN";
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            recognition.onstart = function () {
                activeRecognition = recognition;
                button.classList.add("listening");
                setStatus("Listening…");
            };

            recognition.onresult = function (event) {
                applyResult(button, event.results[0][0].transcript.trim());
            };

            recognition.onerror = function (event) {
                if (event.error === "not-allowed" || event.error === "service-not-allowed") {
                    setStatus("Microphone access was blocked. Check your browser permissions.");
                } else if (event.error === "no-speech") {
                    setStatus("Didn't catch that — please try again.");
                } else if (event.error === "audio-capture") {
                    setStatus("No microphone was found.");
                } else {
                    setStatus("Voice input didn't work — please type instead.");
                }
            };

            recognition.onend = function () {
                button.classList.remove("listening");
                activeRecognition = null;
            };

            try {
                recognition.start();
            } catch (err) {
                setStatus("Voice input didn't start — please type instead.");
            }
        }

        micButtons.forEach(function (button) {
            button.hidden = false;
            button.addEventListener("click", function () {
                startListening(button);
            });
        });
    }

    // ----- 3. Read results aloud --------------------------------------

    function enableReadAloud() {
        var readButton = document.querySelector(".btn-read");
        if (!readButton) {
            return; // not on a results page with jobs
        }

        // Graceful fallback: no SpeechSynthesis API — button stays hidden.
        var synth = window.speechSynthesis;
        if (!synth || typeof window.SpeechSynthesisUtterance !== "function") {
            return;
        }

        var readLabel = readButton.textContent;                 // current language
        var stopLabel = readButton.getAttribute("data-stop-label") || "Stop reading";

        function resetButton() {
            readButton.textContent = readLabel;
            readButton.classList.remove("speaking");
        }

        // Build a short spoken summary from what is on the page.
        function buildLines() {
            var lines = [];
            var heading = document.querySelector(".results-title");
            var count = document.querySelector(".results-count");
            if (heading) {
                lines.push(clean(heading.textContent));
            }
            if (count) {
                lines.push(clean(count.textContent));
            }
            document.querySelectorAll(".job-card").forEach(function (card, index) {
                var title = card.querySelector(".job-title");
                var meta = card.querySelector(".job-meta");
                var line = "Result " + (index + 1) + ": " + (title ? clean(title.textContent) : "");
                if (meta) {
                    line += ". " + clean(meta.textContent);
                }
                lines.push(line);
            });
            return lines;
        }

        function clean(text) {
            return (text || "").replace(/\s+/g, " ").trim();
        }

        function speak() {
            // Speak one short utterance per line — keeps each request small
            // and sidesteps the long-text cut-off some browsers have.
            var lines = buildLines();
            lines.forEach(function (line, index) {
                var utterance = new SpeechSynthesisUtterance(line);
                utterance.lang = "en-IN";
                if (index === lines.length - 1) {
                    utterance.onend = resetButton;
                }
                utterance.onerror = resetButton;
                synth.speak(utterance);
            });
            readButton.textContent = stopLabel;
            readButton.classList.add("speaking");
        }

        readButton.hidden = false;

        readButton.addEventListener("click", function () {
            if (synth.speaking || synth.pending) {
                synth.cancel();
                resetButton();
            } else {
                speak();
            }
        });

        // Stop speech when leaving the page, and reset on Back navigation.
        window.addEventListener("pagehide", function () {
            synth.cancel();
        });
        window.addEventListener("pageshow", resetButton);
    }
})();
