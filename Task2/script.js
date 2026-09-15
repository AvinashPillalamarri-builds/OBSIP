/**
 * ==========================================================================
 * SecurePass — Random Password Generator
 * Core Cryptographic & UI Script
 * ==========================================================================
 */

(function () {
  'use strict';

  // --- CHARACTER SET DEFINITIONS ---
  const CHAR_SETS = {
    upper: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    lower: 'abcdefghijklmnopqrstuvwxyz',
    numbers: '0123456789',
    symbols: '!@#$%^&*()-_=+[]{};:,.?'
  };

  const AMBIGUOUS_CHARS = ['0', 'O', 'o', '1', 'l', 'I'];

  // --- APPLICATION STATE ---
  let history = []; // Session-only password history (max 5 items)
  let historyMaskStates = []; // Track visibility toggle for history items

  // --- DOM ELEMENT REFERENCES ---
  const passwordOutput = document.getElementById('passwordOutput');
  const toggleVisibilityBtn = document.getElementById('toggleVisibilityBtn');
  const visibilityIcon = document.getElementById('visibilityIcon');

  const copyBtn = document.getElementById('copyBtn');
  const copyBtnText = document.getElementById('copyBtnText');
  const copyIcon = document.getElementById('copyIcon');
  const generateBtn = document.getElementById('generateBtn');
  const resetBtn = document.getElementById('resetBtn');

  const validationAlert = document.getElementById('validationAlert');
  const validationMessage = document.getElementById('validationMessage');

  const strengthLabel = document.getElementById('strengthLabel');
  const strengthMeterFill = document.getElementById('strengthMeterFill');

  const lengthSlider = document.getElementById('lengthSlider');
  const lengthInput = document.getElementById('lengthInput');

  const chkUpper = document.getElementById('chkUpper');
  const chkLower = document.getElementById('chkLower');
  const chkNumbers = document.getElementById('chkNumbers');
  const chkSymbols = document.getElementById('chkSymbols');
  const chkExcludeAmbiguous = document.getElementById('chkExcludeAmbiguous');

  const historyCard = document.querySelector('.history-card');
  const historyEmpty = document.getElementById('historyEmpty');
  const historyList = document.getElementById('historyList');
  const clearHistoryBtn = document.getElementById('clearHistoryBtn');

  let isMainPasswordVisible = true;

  // --- CRYPTOGRAPHICALLY SECURE RANDOM GENERATOR ---
  /**
   * Generates an unbiased random integer in the range [0, max) using Web Crypto API.
   * Uses rejection sampling to eliminate modulo bias.
   * @param {number} max - Upper bound (exclusive)
   * @returns {number} Unbiased random integer
   */
  function getSecureRandomInt(max) {
    if (max <= 0) return 0;
    const maxUint32 = 0xFFFFFFFF;
    // Highest multiple of max that fits in uint32
    const limit = maxUint32 - (maxUint32 % max);
    const array = new Uint32Array(1);
    let rand;
    
    // Rejection sampling loop
    do {
      window.crypto.getRandomValues(array);
      rand = array[0];
    } while (rand >= limit);

    return rand % max;
  }

  /**
   * Securely shuffles an array in-place using Fisher-Yates and Web Crypto API.
   * @param {Array} array 
   * @returns {Array} Shuffled array
   */
  function shuffleSecurely(array) {
    for (let i = array.length - 1; i > 0; i--) {
      const j = getSecureRandomInt(i + 1);
      const temp = array[i];
      array[i] = array[j];
      array[j] = temp;
    }
    return array;
  }

  // --- FILTERING & HELPER FUNCTIONS ---
  /**
   * Filters ambiguous characters from a string if enabled.
   * @param {string} str 
   * @param {boolean} exclude 
   * @returns {string} Filtered string
   */
  function cleanCharSet(str, exclude) {
    if (!exclude) return str;
    return str.split('').filter(ch => !AMBIGUOUS_CHARS.includes(ch)).join('');
  }

  /**
   * Collects current user settings from the UI.
   * @returns {Object} Settings object
   */
  function getSettings() {
    return {
      length: parseInt(lengthInput.value, 10),
      upper: chkUpper.checked,
      lower: chkLower.checked,
      numbers: chkNumbers.checked,
      symbols: chkSymbols.checked,
      excludeAmbiguous: chkExcludeAmbiguous.checked
    };
  }

  /**
   * Validates user settings.
   * @param {Object} settings 
   * @returns {Object} { isValid: boolean, errorMsg: string }
   */
  function validateSettings(settings) {
    if (isNaN(settings.length) || settings.length < 8 || settings.length > 64) {
      return { isValid: false, errorMsg: 'Password length must be between 8 and 64 characters.' };
    }

    const selectedTypesCount = [settings.upper, settings.lower, settings.numbers, settings.symbols].filter(Boolean).length;
    if (selectedTypesCount < 2) {
      return { isValid: false, errorMsg: 'Please select at least two character types.' };
    }

    // Verify character sets aren't empty after ambiguous character exclusion
    if (settings.upper && cleanCharSet(CHAR_SETS.upper, settings.excludeAmbiguous).length === 0) {
      return { isValid: false, errorMsg: 'Uppercase set is empty after excluding ambiguous characters.' };
    }
    if (settings.lower && cleanCharSet(CHAR_SETS.lower, settings.excludeAmbiguous).length === 0) {
      return { isValid: false, errorMsg: 'Lowercase set is empty after excluding ambiguous characters.' };
    }
    if (settings.numbers && cleanCharSet(CHAR_SETS.numbers, settings.excludeAmbiguous).length === 0) {
      return { isValid: false, errorMsg: 'Numbers set is empty after excluding ambiguous characters.' };
    }
    if (settings.symbols && cleanCharSet(CHAR_SETS.symbols, settings.excludeAmbiguous).length === 0) {
      return { isValid: false, errorMsg: 'Symbols set is empty after excluding ambiguous characters.' };
    }

    return { isValid: true, errorMsg: '' };
  }

  // --- PASSWORD GENERATION ALGORITHM ---
  /**
   * Core function to generate a password according to settings.
   * Guarantees at least 1 character from EVERY selected character type.
   * @returns {string|null} Generated password or null if invalid settings
   */
  function generatePassword() {
    const settings = getSettings();
    const validation = validateSettings(settings);

    if (!validation.isValid) {
      showValidationError(validation.errorMsg);
      passwordOutput.value = '';
      updateStrengthIndicator('', 0, 0);
      return null;
    }

    hideValidationError();

    // Prepare active character pools
    const activePools = [];
    if (settings.upper) activePools.push(cleanCharSet(CHAR_SETS.upper, settings.excludeAmbiguous));
    if (settings.lower) activePools.push(cleanCharSet(CHAR_SETS.lower, settings.excludeAmbiguous));
    if (settings.numbers) activePools.push(cleanCharSet(CHAR_SETS.numbers, settings.excludeAmbiguous));
    if (settings.symbols) activePools.push(cleanCharSet(CHAR_SETS.symbols, settings.excludeAmbiguous));

    const passwordChars = [];

    // Step 1: Pick at least ONE character from EVERY selected character type
    activePools.forEach(pool => {
      const randomIndex = getSecureRandomInt(pool.length);
      passwordChars.push(pool[randomIndex]);
    });

    // Step 2: Combine all active pools into one full character pool
    const combinedPool = activePools.join('');

    // Step 3: Fill remaining positions up to requested length
    const remainingCount = settings.length - passwordChars.length;
    for (let i = 0; i < remainingCount; i++) {
      const randomIndex = getSecureRandomInt(combinedPool.length);
      passwordChars.push(combinedPool[randomIndex]);
    }

    // Step 4: Cryptographically shuffle the resulting array
    shuffleSecurely(passwordChars);

    const resultPassword = passwordChars.join('');

    // Update UI Password Display
    passwordOutput.value = isMainPasswordVisible ? resultPassword : '•'.repeat(resultPassword.length);
    passwordOutput.dataset.rawPassword = resultPassword;

    // Update Password Strength
    const strength = calculatePasswordStrength(resultPassword, activePools.length, settings.length, combinedPool.length);
    updateStrengthIndicator(strength.label, strength.score, strength.percentage);

    // Add to Recent Passwords History
    addToHistory(resultPassword);

    // Attempt automatic clipboard copy
    autoCopyToClipboard(resultPassword);

    return resultPassword;
  }

  // --- STRENGTH INDICATOR LOGIC ---
  /**
   * Calculates password strength metrics.
   * @param {string} password 
   * @param {number} typeCount 
   * @param {number} length 
   * @param {number} poolSize 
   * @returns {Object} { label: string, score: number, percentage: number }
   */
  function calculatePasswordStrength(password, typeCount, length, poolSize) {
    if (!password) return { label: 'Weak', score: 1, percentage: 0 };

    // Calculate information entropy in bits: E = length * log2(poolSize)
    const entropy = length * Math.log2(poolSize || 1);

    let label = 'Weak';
    let percentage = 33;
    let score = 1;

    // Rule heuristic:
    // Strong: length >= 16 AND at least 3 types (or entropy >= 75 bits)
    // Medium: length 11-15 OR at least 3 types (or entropy >= 50 bits)
    // Weak: length 8-10 or only 2 types with short length
    if (length >= 16 && typeCount >= 3) {
      label = 'Strong';
      percentage = 100;
      score = 3;
    } else if (entropy >= 80) {
      label = 'Strong';
      percentage = 100;
      score = 3;
    } else if ((length >= 11 && typeCount >= 2) || (length >= 8 && typeCount >= 3) || entropy >= 50) {
      label = 'Medium';
      percentage = 66;
      score = 2;
    } else {
      label = 'Weak';
      percentage = 33;
      score = 1;
    }

    return { label, score, percentage };
  }

  /**
   * Updates visual strength meter UI.
   * @param {string} label 
   * @param {number} score 
   * @param {number} percentage 
   */
  function updateStrengthIndicator(label, score, percentage) {
    strengthLabel.textContent = label;
    strengthLabel.className = 'strength-badge';
    strengthMeterFill.className = 'meter-fill';

    if (label === 'Strong') {
      strengthLabel.classList.add('strength-strong');
      strengthMeterFill.classList.add('fill-strong');
    } else if (label === 'Medium') {
      strengthLabel.classList.add('strength-medium');
      strengthMeterFill.classList.add('fill-medium');
    } else {
      strengthLabel.classList.add('strength-weak');
      strengthMeterFill.classList.add('fill-weak');
    }

    strengthMeterFill.style.width = `${percentage}%`;
  }

  // --- VALIDATION ALERT UI ---
  function showValidationError(message) {
    validationMessage.textContent = message;
    validationAlert.classList.remove('hidden');
  }

  function hideValidationError() {
    validationAlert.classList.add('hidden');
  }

  // --- CLIPBOARD ACTIONS ---
  /**
   * Copies text to clipboard with button feedback UI.
   * @param {string} text 
   * @param {HTMLElement} btn 
   * @param {HTMLElement} btnText 
   */
  function copyToClipboard(text, btn, btnText) {
    if (!text) return;

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(onSuccess, fallbackCopy);
    } else {
      fallbackCopy();
    }

    function fallbackCopy() {
      try {
        const tempInput = document.createElement('textarea');
        tempInput.value = text;
        tempInput.style.position = 'fixed';
        tempInput.style.opacity = '0';
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        onSuccess();
      } catch (err) {
        console.warn('Clipboard write failed:', err);
      }
    }

    function onSuccess() {
      if (btn && btnText) {
        const originalText = btnText.textContent;
        btnText.textContent = '✓ Copied!';
        btn.classList.add('copied');

        setTimeout(() => {
          btnText.textContent = originalText;
          btn.classList.remove('copied');
        }, 2000);
      }
    }
  }

  /**
   * Auto-copies password to clipboard upon generation (silently fails if browser blocks permission).
   * @param {string} password 
   */
  function autoCopyToClipboard(password) {
    if (!password || !navigator.clipboard || !navigator.clipboard.writeText) return;
    navigator.clipboard.writeText(password).catch(() => {
      // Intentionally ignore background clipboard errors to prevent breaking app flow
    });
  }

  // --- HISTORY MANAGEMENT ---
  /**
   * Adds a generated password to in-memory session history (max 5 items, newest first).
   * @param {string} password 
   */
  function addToHistory(password) {
    if (!password) return;

    // Avoid duplicate top entry
    if (history.length > 0 && history[0] === password) return;

    history.unshift(password);
    historyMaskStates.unshift(true); // Masked by default

    if (history.length > 5) {
      history.pop();
      historyMaskStates.pop();
    }

    renderHistory();
  }

  /**
   * Renders the session history list UI.
   */
  function renderHistory() {
    if (history.length === 0) {
      historyEmpty.classList.remove('hidden');
      historyList.classList.add('hidden');
      historyList.innerHTML = '';
      return;
    }

    historyEmpty.classList.add('hidden');
    historyList.classList.remove('hidden');
    historyList.innerHTML = '';

    history.forEach((pwd, idx) => {
      const li = document.createElement('li');
      li.className = 'history-item';

      const isMasked = historyMaskStates[idx];
      const displayPwd = isMasked ? '•'.repeat(pwd.length) : pwd;

      li.innerHTML = `
        <div class="history-pass-wrapper">
          <span class="history-password-text">${escapeHtml(displayPwd)}</span>
        </div>
        <div class="history-item-actions">
          <button type="button" class="icon-btn hist-toggle-btn" title="Show/Hide" aria-label="Toggle password visibility">
            ${isMasked ? '👁️' : '🙈'}
          </button>
          <button type="button" class="btn btn-sm btn-primary hist-copy-btn" title="Copy to clipboard">
            📋 Copy
          </button>
        </div>
      `;

      // Event listeners for history item buttons
      const toggleBtn = li.querySelector('.hist-toggle-btn');
      const copyHistBtn = li.querySelector('.hist-copy-btn');

      toggleBtn.addEventListener('click', () => {
        historyMaskStates[idx] = !historyMaskStates[idx];
        renderHistory();
      });

      copyHistBtn.addEventListener('click', () => {
        copyToClipboard(pwd, copyHistBtn, copyHistBtn);
      });

      historyList.appendChild(li);
    });
  }

  function clearHistory() {
    history = [];
    historyMaskStates = [];
    renderHistory();
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // --- RESET SETTINGS ---
  function resetSettings() {
    lengthSlider.value = 16;
    lengthInput.value = 16;
    chkUpper.checked = true;
    chkLower.checked = true;
    chkNumbers.checked = true;
    chkSymbols.checked = true;
    chkExcludeAmbiguous.checked = false;

    isMainPasswordVisible = true;
    visibilityIcon.textContent = '👁️';

    generatePassword();
  }

  // --- EVENT BINDINGS & INITIALIZATION ---
  function initEvents() {
    // Synchronize slider and spinbox length inputs
    lengthSlider.addEventListener('input', (e) => {
      lengthInput.value = e.target.value;
      generatePassword();
    });

    lengthInput.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      if (!isNaN(val) && val >= 8 && val <= 64) {
        lengthSlider.value = val;
      }
      generatePassword();
    });

    lengthInput.addEventListener('blur', () => {
      let val = parseInt(lengthInput.value, 10);
      if (isNaN(val) || val < 8) val = 8;
      if (val > 64) val = 64;
      lengthInput.value = val;
      lengthSlider.value = val;
      generatePassword();
    });

    // Checkbox change triggers regeneration
    [chkUpper, chkLower, chkNumbers, chkSymbols, chkExcludeAmbiguous].forEach(chk => {
      chk.addEventListener('change', generatePassword);
    });

    // Generate Button
    generateBtn.addEventListener('click', generatePassword);

    // Main Copy Button
    copyBtn.addEventListener('click', () => {
      const rawPwd = passwordOutput.dataset.rawPassword || passwordOutput.value;
      copyToClipboard(rawPwd, copyBtn, copyBtnText);
    });

    // Main Visibility Toggle Button
    toggleVisibilityBtn.addEventListener('click', () => {
      isMainPasswordVisible = !isMainPasswordVisible;
      visibilityIcon.textContent = isMainPasswordVisible ? '👁️' : '🙈';
      const rawPwd = passwordOutput.dataset.rawPassword || '';
      if (rawPwd) {
        passwordOutput.value = isMainPasswordVisible ? rawPwd : '•'.repeat(rawPwd.length);
      }
    });

    // Reset Button
    resetBtn.addEventListener('click', resetSettings);

    // Clear History Button
    clearHistoryBtn.addEventListener('click', clearHistory);
  }

  // Initial setup on page load
  document.addEventListener('DOMContentLoaded', () => {
    initEvents();
    generatePassword();
  });

})();
