/**
 * MailBear Form Handler v2.0.0
 * Form ID: {{ form_id }}
 * Generated: {{ generation_timestamp }}
 */
(function() {
    'use strict';

    // Form Configuration
    const config = {
        formId: '{{ form_id }}',
        apiEndpoint: '{{ api_endpoint }}',
        formSelector: '[data-mailbear="{{ form_id }}"]',
        honeypotEnabled: {{ honeypot_enabled|lower }},
        honeypotField: '{{ honeypot_field }}',
        redirectUrl: '{{ redirect_url }}',
        successMessage: '{{ success_message|safe }}',
        errorMessage: '{{ error_message|safe }}',
        validationEnabled: {{ validation_enabled|lower }},
        submitTimeout: {{ submit_timeout }},
        csrfEnabled: {{ csrf_enabled|lower }},
        fileUploadEnabled: {{ file_upload_enabled|lower }},
        allowedFileTypes: [{{ allowed_file_types|safe }}],
        maxFileSize: {{ max_file_size }},
        debug: {{ debug|lower }},
        multiStepEnabled: {{ multi_step_enabled|lower }},
        steps: {{ steps|safe }},
        stepConditions: {{ step_conditions|safe }}
    };

    // Core functionality
    let form = null;
    let messageContainer = null;
    let submitting = false;
    
    /**
     * Initialize the form handler
     */
    function init() {
        form = document.querySelector(config.formSelector);
        
        if (!form) {
            debug(`Form with selector "${config.formSelector}" not found`);
            return;
        }

        // Add honeypot if enabled
        if (config.honeypotEnabled && config.honeypotField) {
            addHoneypot();
        }
        
        // Create a message container for feedback
        createMessageContainer();
        
        // Set up multi-step form if enabled
        if (config.multiStepEnabled && config.steps && config.steps.length > 0) {
            setupMultiStepForm();
        } else {
            // Single-step form setup
            form.addEventListener('submit', handleSubmit);
        }
        
        // Initialize file upload handling if enabled
        if (config.fileUploadEnabled) {
            setupFileUpload();
        }
        
        debug('Form handler initialized');
    }
    
    /**
     * Debug logging
     */
    function debug(message, data) {
        if (config.debug) {
            console.log(`[MailBear] ${message}`, data || '');
        }
    }

    /**
     * Create a simple message container
     */
    function createMessageContainer() {
        messageContainer = document.createElement('div');
        messageContainer.className = 'mailbear-message';
        messageContainer.style.display = 'none';
        form.appendChild(messageContainer);
    }
    
    /**
     * Add a simple honeypot field
     */
    function addHoneypot() {
        const honeypotWrapper = document.createElement('div');
        honeypotWrapper.style.opacity = '0';
        honeypotWrapper.style.position = 'absolute';
        honeypotWrapper.style.height = '0';
        honeypotWrapper.style.overflow = 'hidden';
        
        const input = document.createElement('input');
        input.type = 'text';
        input.name = config.honeypotField;
        input.tabIndex = '-1';
        input.autocomplete = 'off';
        
        honeypotWrapper.appendChild(input);
        form.appendChild(honeypotWrapper);
    }
    
    /**
     * Handle form submission
     */
    function handleSubmit(event) {
        event.preventDefault();
        
        if (submitting) return;
        
        // Clear previous messages
        hideMessage();
        
        // Validate if enabled
        if (config.validationEnabled && !form.checkValidity()) {
            form.reportValidity();
            return;
        }
        
        // Set submitting state
        submitting = true;
        setSubmitButtonState(true, 'Sending...');
        
        // Submit the form data
        submitForm(new FormData(form));
    }
    
    /**
     * Submit form data to API
     */
    function submitForm(formData) {
        let timeoutId;
        
        // Set timeout
        timeoutId = setTimeout(() => {
            submitting = false;
            setSubmitButtonState(false);
            showMessage('Submission timed out. Please try again.', 'error');
        }, config.submitTimeout);
        
        fetch(config.apiEndpoint, {
            method: 'POST',
            body: formData,
            headers: {
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (timeoutId) clearTimeout(timeoutId);
            
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.message || 'Submission failed');
                });
            }
            
            return response.json();
        })
        .then(data => {
            submitting = false;
            setSubmitButtonState(false);
            
            if (data.status === 'success') {
                handleSuccess(data);
            } else {
                showMessage(data.message || 'Submission failed', 'error');
            }
        })
        .catch(error => {
            if (timeoutId) clearTimeout(timeoutId);
            submitting = false;
            setSubmitButtonState(false);
            showMessage(error.message || 'An unexpected error occurred', 'error');
            debug('Submission error:', error);
        });
    }
    
    /**
     * Handle successful submission
     */
    function handleSuccess(data) {
        // Show success message if provided
        if (config.successMessage) {
            showMessage(config.successMessage, 'success');
        }
        
        // Reset form
        form.reset();
        
        // Clear any file inputs
        clearFileInputs();
        
        // Redirect if URL provided
        if (config.redirectUrl) {
            setTimeout(() => {
                window.location.href = config.redirectUrl;
            }, 1000);
        }
        
        // Trigger success event
        triggerEvent('mailbear:success', data);
    }
    
    /**
     * Clear file inputs
     */
    function clearFileInputs() {
        if (!config.fileUploadEnabled) return;
        
        const fileInputs = form.querySelectorAll('input[type="file"]');
        fileInputs.forEach(input => {
            input.value = '';
            // Clear any preview elements if they exist
            const previewEl = input.nextElementSibling;
            if (previewEl && previewEl.classList.contains('mailbear-file-preview')) {
                previewEl.innerHTML = '';
            }
        });
    }
    
    /**
     * Set submit button state
     */
    function setSubmitButtonState(isLoading, loadingText) {
        const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
        if (!submitButton) return;
        
        submitButton.disabled = isLoading;
        
        if (isLoading) {
            submitButton.dataset.originalText = submitButton.innerText;
            submitButton.innerText = loadingText || 'Sending...';
        } else if (submitButton.dataset.originalText) {
            submitButton.innerText = submitButton.dataset.originalText;
        }
    }
    
    /**
     * Show message to user
     */
    function showMessage(message, type) {
        if (!messageContainer) return;
        
        messageContainer.className = `mailbear-message mailbear-${type}`;
        messageContainer.innerHTML = message;
        messageContainer.style.display = 'block';
        
        // Scroll to message
        messageContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    /**
     * Hide message
     */
    function hideMessage() {
        if (!messageContainer) return;
        
        messageContainer.style.display = 'none';
        messageContainer.innerHTML = '';
    }
    
    /**
     * Set up multi-step form
     */
    function setupMultiStepForm() {
        const stepData = createStepContainers();
        const { steps, navButtons } = stepData;
        
        // Add navigation events
        navButtons.forEach(button => {
            button.addEventListener('click', () => {
                const direction = button.dataset.direction;
                const currentStep = parseInt(form.dataset.currentStep) || 0;
                
                if (direction === 'next') {
                    // Validate current step
                    if (config.validationEnabled && !validateStep(steps[currentStep])) {
                        return;
                    }
                    
                    // Go to next step
                    showStep(currentStep + 1, steps);
                } else if (direction === 'prev') {
                    // Go to previous step
                    showStep(currentStep - 1, steps);
                }
            });
        });
        
        // Add submit handler for final step
        form.addEventListener('submit', event => {
            event.preventDefault();
            
            const currentStep = parseInt(form.dataset.currentStep) || 0;
            
            // Validate current step
            if (config.validationEnabled && !validateStep(steps[currentStep])) {
                return;
            }
            
            // Submit form
            handleSubmit(event);
        });
        
        // Show first step
        showStep(0, steps);
    }
    
    /**
     * Create step containers for multi-step form
     */
    function createStepContainers() {
        const steps = [];
        const navButtons = [];
        
        // Create containers for each step
        config.steps.forEach((stepConfig, index) => {
            const isLastStep = index === config.steps.length - 1;
            
            // Create step container
            const step = document.createElement('div');
            step.className = 'mailbear-step';
            step.dataset.step = index;
            step.style.display = 'none';
            
            // Add step fields
            if (stepConfig.fields && stepConfig.fields.length > 0) {
                const formElements = Array.from(form.elements);
                
                stepConfig.fields.forEach(fieldName => {
                    const field = findFormField(formElements, fieldName);
                    if (field) {
                        // Get the field's container (usually a parent element)
                        let fieldContainer = field;
                        
                        // Try to find a suitable parent container
                        let parent = field.parentElement;
                        while (parent && parent !== form && !parent.classList.contains('form-group')) {
                            fieldContainer = parent;
                            parent = parent.parentElement;
                        }
                        
                        // Move to this step
                        step.appendChild(fieldContainer.cloneNode(true));
                        fieldContainer.style.display = 'none';
                    }
                });
            }
            
            // Add navigation buttons
            const nav = document.createElement('div');
            nav.className = 'mailbear-step-nav';
            
            // Previous button (except for first step)
            if (index > 0) {
                const prevButton = document.createElement('button');
                prevButton.type = 'button';
                prevButton.className = 'mailbear-prev-button';
                prevButton.innerText = 'Previous';
                prevButton.dataset.direction = 'prev';
                navButtons.push(prevButton);
                nav.appendChild(prevButton);
            }
            
            // Next button or submit button
            if (!isLastStep) {
                const nextButton = document.createElement('button');
                nextButton.type = 'button';
                nextButton.className = 'mailbear-next-button';
                nextButton.innerText = 'Next';
                nextButton.dataset.direction = 'next';
                navButtons.push(nextButton);
                nav.appendChild(nextButton);
            } else {
                // For the last step, use the form's submit button
                const submitButton = form.querySelector('button[type="submit"], input[type="submit"]');
                if (submitButton) {
                    nav.appendChild(submitButton.cloneNode(true));
                    submitButton.style.display = 'none';
                }
            }
            
            step.appendChild(nav);
            form.appendChild(step);
            steps.push(step);
        });
        
        return { steps, navButtons };
    }
    
    /**
     * Find a form field by name or id
     */
    function findFormField(elements, fieldName) {
        return elements.find(el => 
            el.name === fieldName || 
            el.id === fieldName
        );
    }
    
    /**
     * Validate a single step
     */
    function validateStep(stepEl) {
        const inputs = stepEl.querySelectorAll('input, select, textarea');
        let isValid = true;
        
        inputs.forEach(input => {
            if (input.required && !input.value.trim()) {
                input.classList.add('mailbear-error');
                isValid = false;
            } else {
                input.classList.remove('mailbear-error');
            }
            
            // Validate email fields
            if (input.type === 'email' && input.value) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(input.value)) {
                    input.classList.add('mailbear-error');
                    isValid = false;
                }
            }
        });
        
        return isValid;
    }
    
    /**
     * Show a specific step
     */
    function showStep(stepIndex, steps) {
        if (stepIndex < 0 || stepIndex >= steps.length) {
            return;
        }
        
        // Hide all steps
        steps.forEach(step => {
            step.style.display = 'none';
        });
        
        // Show current step
        steps[stepIndex].style.display = 'block';
        
        // Update form data attribute
        form.dataset.currentStep = stepIndex;
        
        // Trigger step change event
        triggerEvent('mailbear:step-change', { stepIndex });
    }
    
    /**
     * Set up file upload handling
     */
    function setupFileUpload() {
        const fileInputs = form.querySelectorAll('input[type="file"]');
        
        fileInputs.forEach(input => {
            // Add change listener for previews
            input.addEventListener('change', () => {
                // Get or create preview container
                let previewEl = input.nextElementSibling;
                if (!previewEl || !previewEl.classList.contains('mailbear-file-preview')) {
                    previewEl = document.createElement('div');
                    previewEl.className = 'mailbear-file-preview';
                    input.insertAdjacentElement('afterend', previewEl);
                }
                
                // Clear previous previews
                previewEl.innerHTML = '';
                
                // Check files
                if (!input.files || input.files.length === 0) {
                    return;
                }
                
                // Create simple file list
                const fileList = document.createElement('ul');
                
                Array.from(input.files).forEach(file => {
                    // Check file size
                    if (file.size > config.maxFileSize * 1024 * 1024) {
                        showMessage(`File ${file.name} exceeds maximum size of ${config.maxFileSize}MB`, 'error');
                        input.value = '';
                        return;
                    }
                    
                    // Check file type
                    if (config.allowedFileTypes.length > 0) {
                        const fileExt = file.name.split('.').pop().toLowerCase();
                        if (!config.allowedFileTypes.includes(fileExt)) {
                            showMessage(`File type .${fileExt} is not allowed`, 'error');
                            input.value = '';
                            return;
                        }
                    }
                    
                    // Add file to list
                    const listItem = document.createElement('li');
                    listItem.textContent = `${file.name} (${formatFileSize(file.size)})`;
                    fileList.appendChild(listItem);
                });
                
                previewEl.appendChild(fileList);
            });
        });
    }
    
    /**
     * Format file size
     */
    function formatFileSize(bytes) {
        if (bytes < 1024) {
            return bytes + ' B';
        } else if (bytes < 1024 * 1024) {
            return (bytes / 1024).toFixed(1) + ' KB';
        } else {
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }
    }
    
    /**
     * Trigger a custom event
     */
    function triggerEvent(name, detail) {
        const event = new CustomEvent(name, {
            bubbles: true,
            detail: detail
        });
        
        form.dispatchEvent(event);
    }

    // Initialize
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();