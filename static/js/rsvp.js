/**
 * Shared RSVP functionality for Cosy Polyamory events
 * Used by both events list and event detail pages
 */

// Initialize RSVP functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeRSVPHandlers();
});

function initializeRSVPHandlers() {
    // Handle attendance button clicks for initial selection (three-button layout)
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('attendance-btn')) {
            e.preventDefault();
            const eventId = e.target.getAttribute('data-event-id');
            const status = e.target.getAttribute('data-status');
            
            if (eventId && status && !e.target.disabled) {
                updateAttendanceStatusFromButton(eventId, status, e.target);
            }
        }
    });

    // Handle attendance dropdown item clicks (for changing existing RSVP)
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('attendance-dropdown-item')) {
            e.preventDefault();
            const eventId = e.target.getAttribute('data-event-id');
            const status = e.target.getAttribute('data-status');
            
            if (eventId && status) {
                updateAttendanceStatusFromDropdown(eventId, status, e.target);
            }
        }
    });
}

/**
 * Handle RSVP from initial three-button click
 */
function updateAttendanceStatusFromButton(eventId, status, button) {
    // Find the button group for this event
    const buttonGroup = button.closest('.btn-group');
    if (!buttonGroup) return;
    
    // Show loading state - disable all buttons in the group
    const allButtons = buttonGroup.querySelectorAll('.attendance-btn');
    allButtons.forEach(btn => {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Loading...';
    });

    // Make AJAX request
    makeRSVPRequest(eventId, status)
        .then(data => {
            if (data.success) {
                updateDropdownState(buttonGroup, data.status, eventId);
                updateAttendeeInfo(eventId, data);
                showToast(data.message, 'success');
            } else {
                showToast(data.message, 'error');
                // Restore buttons on error
                allButtons.forEach((btn, index) => {
                    btn.disabled = false;
                    const originalTexts = ['Yes', 'No', 'Maybe'];
                    btn.innerHTML = originalTexts[index];
                });
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('An error occurred while updating your attendance.', 'error');
            // Restore buttons on error
            allButtons.forEach((btn, index) => {
                btn.disabled = false;
                const originalTexts = ['Yes', 'No', 'Maybe'];
                btn.innerHTML = originalTexts[index];
            });
        });
}

/**
 * Handle RSVP from dropdown item click
 */
function updateAttendanceStatusFromDropdown(eventId, status, dropdownItem) {
    // Find the dropdown button for this event
    const dropdownButton = document.querySelector(`#rsvpDropdown${eventId}`);
    if (!dropdownButton) return;
    
    // Show loading state
    const originalText = dropdownButton.innerHTML;
    dropdownButton.disabled = true;
    dropdownButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Updating...';

    // Make AJAX request
    makeRSVPRequest(eventId, status)
        .then(data => {
            if (data.success) {
                updateDropdownState(dropdownButton, data.status, eventId);
                updateAttendeeInfo(eventId, data);
                showToast(data.message, 'success');
            } else {
                showToast(data.message, 'error');
                dropdownButton.innerHTML = originalText;
            }
            dropdownButton.disabled = false;
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('An error occurred while updating your attendance.', 'error');
            dropdownButton.innerHTML = originalText;
            dropdownButton.disabled = false;
        });
}

/**
 * Make AJAX request to update RSVP status
 */
function makeRSVPRequest(eventId, status) {
    return fetch(`/events/${eventId}/rsvp`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        },
        body: `status=${status}`
    })
    .then(response => response.json());
}

/**
 * Update the dropdown state after successful RSVP
 * Works for both button groups and individual dropdowns
 */
function updateDropdownState(elementOrButton, newStatus, eventId) {
    // Find the attendance container
    const attendanceContainer = elementOrButton.closest('.attendance-container');
    if (!attendanceContainer) return;
    
    // Detect button size classes from existing buttons
    const existingButtons = attendanceContainer.querySelectorAll('button');
    let buttonSizeClass = '';
    let dropdownSizeClass = '';
    let buttonWidthClass = '';
    let minWidthStyle = '';
    
    if (existingButtons.length > 0) {
        const firstButton = existingButtons[0];
        if (firstButton.classList.contains('btn-sm')) {
            buttonSizeClass = ' btn-sm';
        } else if (firstButton.classList.contains('btn-lg')) {
            buttonSizeClass = ' btn-lg';
        }
        
        // Check for width classes
        if (firstButton.classList.contains('w-100')) {
            buttonWidthClass = ' w-100';
            dropdownSizeClass = ' w-100';
        }
        
        // Check for existing min-width style
        const computedStyle = window.getComputedStyle(firstButton);
        const minWidth = computedStyle.minWidth;
        if (minWidth && minWidth !== 'auto' && minWidth !== '0px') {
            minWidthStyle = ` style="min-width: ${minWidth};"`;
        } else {
            // Default min-width for consistent sizing
            minWidthStyle = ' style="min-width: 100px;"';
        }
    } else {
        // Default min-width for consistent sizing
        minWidthStyle = ' style="min-width: 100px;"';
    }
    
    let dropdownHtml = '';
    
    if (newStatus === 'yes') {
        dropdownHtml = `
            <div class="dropdown${dropdownSizeClass}">
                <button class="btn btn-rsvp-yes dropdown-toggle${buttonSizeClass}${buttonWidthClass}" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false"${minWidthStyle}>
                    Yes
                </button>
                <ul class="dropdown-menu${dropdownSizeClass}" aria-labelledby="rsvpDropdown${eventId}">
                    <li><a class="dropdown-item attendance-dropdown-item" href="#" data-event-id="${eventId}" data-status="no">
                        No
                    </a></li>
                    <li><a class="dropdown-item attendance-dropdown-item" href="#" data-event-id="${eventId}" data-status="maybe">
                        Maybe
                    </a></li>
                </ul>
            </div>
        `;
    } else if (newStatus === 'no') {
        dropdownHtml = `
            <div class="dropdown${dropdownSizeClass}">
                <button class="btn btn-rsvp-no dropdown-toggle${buttonSizeClass}${buttonWidthClass}" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false"${minWidthStyle}>
                    No
                </button>
                <ul class="dropdown-menu${dropdownSizeClass}" aria-labelledby="rsvpDropdown${eventId}">
                    <li><a class="dropdown-item attendance-dropdown-item" href="#" data-event-id="${eventId}" data-status="yes">
                        Yes
                    </a></li>
                    <li><a class="dropdown-item attendance-dropdown-item" href="#" data-event-id="${eventId}" data-status="maybe">
                        Maybe
                    </a></li>
                </ul>
            </div>
        `;
    } else if (newStatus === 'maybe') {
        dropdownHtml = `
            <div class="dropdown${dropdownSizeClass}">
                <button class="btn btn-rsvp-maybe dropdown-toggle${buttonSizeClass}${buttonWidthClass}" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false"${minWidthStyle}>
                    Maybe
                </button>
                <ul class="dropdown-menu${dropdownSizeClass}" aria-labelledby="rsvpDropdown${eventId}">
                    <li><a class="dropdown-item attendance-dropdown-item" href="#" data-event-id="${eventId}" data-status="yes">
                        Yes
                    </a></li>
                    <li><a class="dropdown-item attendance-dropdown-item" href="#" data-event-id="${eventId}" data-status="no">
                        No
                    </a></li>
                </ul>
            </div>
        `;
    } else if (newStatus === 'waitlist') {
        dropdownHtml = `
            <div class="dropdown${dropdownSizeClass}">
                <button class="btn btn-rsvp-waitlisted dropdown-toggle${buttonSizeClass}${buttonWidthClass}" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false"${minWidthStyle}>
                    Waitlisted
                </button>
                <ul class="dropdown-menu${dropdownSizeClass}" aria-labelledby="rsvpDropdown${eventId}">
                    <li><a class="dropdown-item attendance-dropdown-item" href="#" data-event-id="${eventId}" data-status="no">
                        No
                    </a></li>
                    <li><a class="dropdown-item attendance-dropdown-item" href="#" data-event-id="${eventId}" data-status="maybe">
                        Maybe
                    </a></li>
                </ul>
            </div>
        `;
    } else {
        // Fallback case - restore to initial three-button state
        dropdownHtml = `
            <div class="btn-group${dropdownSizeClass}" role="group">
                <button class="btn btn-rsvp-none attendance-btn${buttonSizeClass}" type="button" data-event-id="${eventId}" data-status="yes">
                    Yes
                </button>
                <button class="btn btn-rsvp-none attendance-btn${buttonSizeClass}" type="button" data-event-id="${eventId}" data-status="no">
                    No
                </button>
                <button class="btn btn-rsvp-none attendance-btn${buttonSizeClass}" type="button" data-event-id="${eventId}" data-status="maybe">
                    Maybe
                </button>
            </div>
        `;
    }
    
    attendanceContainer.innerHTML = dropdownHtml;
}

/**
 * Update attendee count and pills after RSVP (events list page specific)
 */
function updateAttendeeInfo(eventId, data) {
    // This function is page-specific and will be overridden by each page
}

/**
 * Show toast notification
 */
function showToast(message, type) {
    // This function is page-specific and will be overridden by each page
    alert(message); // Fallback
}