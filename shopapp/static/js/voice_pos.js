(() => {
  const container = document.querySelector('[data-voice-pos]');
  if (!container) return;

  const form = container.querySelector('[data-voice-pos-form]');
  if (!form) return;

  const toggleBtn = container.querySelector('[data-voice-toggle]');
  const toggleLabel = container.querySelector('[data-voice-toggle-label]');
  const statusEl = container.querySelector('[data-voice-status]');
  const previewWrapper = container.querySelector('[data-voice-preview-wrapper]');
  const previewEl = container.querySelector('[data-voice-transcript-preview]');
  const unsupportedEl = container.querySelector('[data-voice-unsupported]');
  const transcriptInput = form.querySelector('[data-voice-transcript]');

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    if (toggleBtn) toggleBtn.classList.add('d-none');
    if (unsupportedEl) unsupportedEl.classList.remove('d-none');
    if (statusEl) statusEl.textContent = '';
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = form.dataset.voiceLang || 'en-IN';
  recognition.interimResults = true;
  recognition.continuous = true;

  let listening = false;
  let finalTranscript = '';

  const quantityInput = form.querySelector('input[name="quantity"]');
  const discountInput = form.querySelector('input[name="discount"]');
  const paymentSelect = form.querySelector('select[name="payment_method"]');
  const saleTypeSelect = form.querySelector('select[name="sale_type"]');
  const itemSelect = form.querySelector('[data-voice-item]');
  const customerSelect = form.querySelector('select[name="customer_id"]');

  const normalize = (value) =>
    value
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

  const buildOptionIndex = (select) =>
    select
      ? Array.from(select.options || [])
          .filter((opt) => opt.value)
          .map((opt) => ({
            value: opt.value,
            element: opt,
            normalized: normalize(opt.dataset.voiceName || opt.textContent || ''),
          }))
      : [];

  const itemOptions = buildOptionIndex(itemSelect);
  const customerOptions = buildOptionIndex(customerSelect);

  const setStatus = (message, highlight = false) => {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.classList.toggle('text-warning', highlight);
  };

  const updatePreview = (text) => {
    if (!previewEl || !previewWrapper) return;
    if (!text) {
      previewWrapper.classList.add('d-none');
      previewEl.textContent = '';
      return;
    }
    previewWrapper.classList.remove('d-none');
    previewEl.textContent = text;
  };

  const findMatch = (options, transcript) => {
    const normalizedTranscript = ` ${normalize(transcript)} `;
    return options.find((opt) => normalizedTranscript.includes(` ${opt.normalized} `));
  };

  const parseNumeric = (match) => {
    if (!match) return undefined;
    const num = parseFloat(match[1]);
    return Number.isFinite(num) ? num : undefined;
  };

  const applyTranscript = (transcript) => {
    if (!transcript) return;
    const lower = transcript.toLowerCase();

    const quantityMatch =
      lower.match(/(?:quantity|qty|pieces|units)\s*(\d{1,4})/) ||
      lower.match(/(\d{1,4})\s*(?:pieces|units|items|qty)/);
    const discountMatch =
      lower.match(/(?:discount|less|off)\s*(\d+(?:\.\d+)?)/) ||
      lower.match(/(\d+(?:\.\d+)?)\s*(?:rupees|rs)\s*(?:discount|off)/);

    const paymentKeywords = [
      { key: 'cash', aliases: ['cash'] },
      { key: 'upi', aliases: ['upi', 'upi payment', 'g pay', 'google pay', 'phonepe', 'bhim'] },
      { key: 'card', aliases: ['card', 'debit', 'credit card'] },
    ];

    const saleType =
      lower.includes('udhar') || lower.includes('credit') ? 'udhar' : lower.includes('paid') ? 'paid' : undefined;

    const paymentMethod = paymentKeywords.find((entry) =>
      entry.aliases.some((alias) => lower.includes(alias))
    );

    const itemMatch = findMatch(itemOptions, transcript);
    const customerMatch = findMatch(customerOptions, transcript);

    const quantity = parseNumeric(quantityMatch);
    const discount = parseNumeric(discountMatch);

    if (quantityInput && quantity && quantity > 0) {
      quantityInput.value = Math.max(1, Math.round(quantity));
    }

    if (discountInput && typeof discount === 'number' && discount >= 0) {
      discountInput.value = discount.toFixed(2);
    }

    if (paymentSelect && paymentMethod) {
      paymentSelect.value = paymentMethod.key;
    }

    if (saleTypeSelect && saleType) {
      saleTypeSelect.value = saleType;
    }

    if (itemSelect && itemMatch) {
      itemSelect.value = itemMatch.value;
    }

    if (customerSelect && customerMatch) {
      customerSelect.value = customerMatch.value;
    }
  };

  const startListening = () => {
    if (listening) return;
    listening = true;
    finalTranscript = '';
    transcriptInput.value = '';
    updatePreview('');
    recognition.start();
  };

  const stopListening = () => {
    listening = false;
    recognition.stop();
  };

  recognition.addEventListener('start', () => {
    setStatus('Listening… speak your sale details clearly.', true);
    if (toggleBtn && toggleLabel) {
      toggleBtn.classList.add('active');
      toggleLabel.textContent = 'Stop voice';
    }
  });

  recognition.addEventListener('result', (event) => {
    let interimTranscript = '';

    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i];
      if (result.isFinal) {
        finalTranscript = `${finalTranscript} ${result[0].transcript}`.trim();
        applyTranscript(finalTranscript);
      } else {
        interimTranscript = `${interimTranscript} ${result[0].transcript}`.trim();
      }
    }

    const combined = [finalTranscript, interimTranscript].filter(Boolean).join(' ').trim();
    transcriptInput.value = combined;
    updatePreview(combined);
  });

  recognition.addEventListener('end', () => {
    if (listening) {
      recognition.start();
      return;
    }
    setStatus('Voice capture paused. Tap the mic to start again.');
    if (toggleBtn && toggleLabel) {
      toggleBtn.classList.remove('active');
      toggleLabel.textContent = 'Start voice';
    }
  });

  recognition.addEventListener('error', (event) => {
    setStatus(`Voice capture error: ${event.error}`, true);
    stopListening();
  });

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      if (listening) {
        stopListening();
      } else {
        startListening();
      }
    });
  }

  setStatus('Tap the mic to fill the form by speaking.');
})();
