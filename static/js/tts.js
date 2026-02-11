/**
 * QuizWeaver - Text-to-Speech Module (BL-032)
 *
 * Uses the browser Web Speech API (speechSynthesis) for client-side
 * text-to-speech. No server-side dependencies.
 */
(function() {
    'use strict';

    // Check for browser support
    if (!('speechSynthesis' in window)) {
        console.warn('[TTS] Speech synthesis not supported in this browser.');
        // Hide TTS UI elements if not supported
        document.querySelectorAll('.tts-panel, .tts-read-btn').forEach(function(el) {
            el.style.display = 'none';
        });
        return;
    }

    var synth = window.speechSynthesis;
    var currentUtterance = null;
    var isPaused = false;
    var currentSpeakingBtn = null;

    // ---- Voice Management ----

    function getVoices() {
        return synth.getVoices().filter(function(v) {
            return v.lang.startsWith('en');
        });
    }

    function populateVoiceDropdown() {
        var select = document.getElementById('ttsVoiceSelect');
        if (!select) return;

        var voices = getVoices();
        select.innerHTML = '';

        if (voices.length === 0) {
            var opt = document.createElement('option');
            opt.textContent = 'Default';
            opt.value = '';
            select.appendChild(opt);
            return;
        }

        voices.forEach(function(voice, i) {
            var opt = document.createElement('option');
            opt.value = i;
            opt.textContent = voice.name + ' (' + voice.lang + ')';
            if (voice.default) opt.selected = true;
            select.appendChild(opt);
        });
    }

    // Voices may load asynchronously
    if (synth.onvoiceschanged !== undefined) {
        synth.onvoiceschanged = populateVoiceDropdown;
    }

    // ---- Speed Control ----

    function getSpeed() {
        var slider = document.getElementById('ttsSpeedSlider');
        return slider ? parseFloat(slider.value) : 1.0;
    }

    function getSelectedVoice() {
        var select = document.getElementById('ttsVoiceSelect');
        if (!select || select.value === '') return null;
        var voices = getVoices();
        return voices[parseInt(select.value)] || null;
    }

    // ---- Core Speech Functions ----

    function speak(text, onEnd) {
        stop();

        var utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = getSpeed();

        var voice = getSelectedVoice();
        if (voice) utterance.voice = voice;

        utterance.onend = function() {
            currentUtterance = null;
            isPaused = false;
            updatePlayButton(false);
            if (currentSpeakingBtn) {
                currentSpeakingBtn.classList.remove('speaking');
                currentSpeakingBtn = null;
            }
            if (onEnd) onEnd();
        };

        utterance.onerror = function(e) {
            if (e.error !== 'canceled') {
                console.warn('[TTS] Speech error:', e.error);
            }
            currentUtterance = null;
            isPaused = false;
            updatePlayButton(false);
            if (currentSpeakingBtn) {
                currentSpeakingBtn.classList.remove('speaking');
                currentSpeakingBtn = null;
            }
        };

        currentUtterance = utterance;
        synth.speak(utterance);
        updatePlayButton(true);
    }

    function pause() {
        if (synth.speaking && !isPaused) {
            synth.pause();
            isPaused = true;
            updatePlayButton(false);
        }
    }

    function resume() {
        if (isPaused) {
            synth.resume();
            isPaused = false;
            updatePlayButton(true);
        }
    }

    function stop() {
        synth.cancel();
        currentUtterance = null;
        isPaused = false;
        updatePlayButton(false);
        if (currentSpeakingBtn) {
            currentSpeakingBtn.classList.remove('speaking');
            currentSpeakingBtn = null;
        }
    }

    function updatePlayButton(isSpeaking) {
        var playBtn = document.getElementById('ttsPlayBtn');
        if (!playBtn) return;
        if (isSpeaking) {
            playBtn.classList.add('active');
            playBtn.setAttribute('aria-label', 'Pause speech');
        } else {
            playBtn.classList.remove('active');
            playBtn.setAttribute('aria-label', 'Play speech');
        }
    }

    // ---- Panel Toggle ----

    function togglePanel() {
        var panel = document.getElementById('ttsPanel');
        if (!panel) return;
        panel.classList.toggle('collapsed');
        var btn = panel.querySelector('.tts-toggle-btn');
        if (btn) {
            var isCollapsed = panel.classList.contains('collapsed');
            btn.setAttribute('aria-expanded', !isCollapsed);
            btn.textContent = isCollapsed ? '+' : '-';
        }
    }

    // ---- Read All Content ----

    function getAllReadableText() {
        var parts = [];
        // Quiz questions
        document.querySelectorAll('.question-card').forEach(function(card) {
            var text = card.querySelector('.question-text');
            if (text) parts.push(text.textContent.trim());
            card.querySelectorAll('.question-options li').forEach(function(li) {
                parts.push(li.textContent.trim());
            });
        });
        // Study cards
        document.querySelectorAll('.card-front-text').forEach(function(el) {
            parts.push(el.textContent.trim());
        });
        document.querySelectorAll('.card-back-text').forEach(function(el) {
            parts.push(el.textContent.trim());
        });
        return parts.join('. ');
    }

    // ---- Per-Item Read Aloud ----

    function readItem(btn) {
        // If this button is currently speaking, stop
        if (currentSpeakingBtn === btn) {
            stop();
            return;
        }

        // Find the parent card/question
        var container = btn.closest('.question-card') || btn.closest('.flip-card') ||
                        btn.closest('.study-section') || btn.closest('.review-item') ||
                        btn.closest('tr');
        if (!container) return;

        var parts = [];
        var textEl = container.querySelector('.question-text');
        if (textEl) parts.push(textEl.textContent.trim());

        container.querySelectorAll('.question-options li').forEach(function(li) {
            parts.push(li.textContent.trim());
        });

        var frontEl = container.querySelector('.card-front-text');
        if (frontEl) parts.push(frontEl.textContent.trim());

        var backEl = container.querySelector('.card-back-text');
        if (backEl) parts.push(backEl.textContent.trim());

        if (parts.length === 0) return;

        currentSpeakingBtn = btn;
        btn.classList.add('speaking');
        speak(parts.join('. '));
    }

    // ---- Event Binding ----

    document.addEventListener('DOMContentLoaded', function() {
        populateVoiceDropdown();

        // Panel toggle
        var panelHeader = document.querySelector('.tts-panel-header');
        if (panelHeader) {
            panelHeader.addEventListener('click', togglePanel);
        }

        // Play/Pause button
        var playBtn = document.getElementById('ttsPlayBtn');
        if (playBtn) {
            playBtn.addEventListener('click', function() {
                if (synth.speaking && !isPaused) {
                    pause();
                } else if (isPaused) {
                    resume();
                } else {
                    speak(getAllReadableText());
                }
            });
        }

        // Stop button
        var stopBtn = document.getElementById('ttsStopBtn');
        if (stopBtn) {
            stopBtn.addEventListener('click', stop);
        }

        // Speed slider
        var speedSlider = document.getElementById('ttsSpeedSlider');
        var speedValue = document.getElementById('ttsSpeedValue');
        if (speedSlider && speedValue) {
            speedSlider.addEventListener('input', function() {
                speedValue.textContent = parseFloat(this.value).toFixed(1) + 'x';
            });
        }

        // Per-item read buttons
        document.querySelectorAll('.tts-read-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                readItem(this);
            });
        });
    });

    // Expose for external use
    window.QWtts = {
        speak: speak,
        pause: pause,
        resume: resume,
        stop: stop,
        readItem: readItem
    };
})();
