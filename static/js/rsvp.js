/**
 * Shared RSVP functionality for Cosy Polyamory events
 * Used by both events list and event detail pages
 */

// Track ongoing RSVP requests to prevent duplicates
const ongoingRequests = new Set();

// Initialize RSVP functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeRSVPHandlers();
});

function initializeRSVPHandlers() {
    // Handle attendance button clicks for initial selection (three-button layout)
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('attendance-btn')) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
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
            e.stopPropagation();
            e.stopImmediatePropagation();
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
    // Check if a request is already in progress for this event
    const requestKey = `${eventId}-${status}`;
    if (ongoingRequests.has(requestKey)) {
        return;
    }
    
    // Find the button group for this event
    const buttonGroup = button.closest('.btn-group');
    if (!buttonGroup) return;
    
    // Show loading state - disable all buttons in the group
    const allButtons = buttonGroup.querySelectorAll('.attendance-btn');
    allButtons.forEach(btn => {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Loading...';
    });

    // Mark request as ongoing
    ongoingRequests.add(requestKey);

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
            showToast('An error occurred while updating your attendance.', 'error');
            // Restore buttons on error
            allButtons.forEach((btn, index) => {
                btn.disabled = false;
                const originalTexts = ['Yes', 'No', 'Maybe'];
                btn.innerHTML = originalTexts[index];
            });
        })
        .finally(() => {
            // Always clear the ongoing request flag
            ongoingRequests.delete(requestKey);
        });
}

/**
 * Handle RSVP from dropdown item click
 */
function updateAttendanceStatusFromDropdown(eventId, status, dropdownItem) {
    // Check if a request is already in progress for this event
    const requestKey = `${eventId}-${status}`;
    if (ongoingRequests.has(requestKey)) {
        return;
    }
    
    // Find the dropdown button for this event
    const dropdownButton = document.querySelector(`#rsvpDropdown${eventId}`);
    if (!dropdownButton) {
        return;
    }
    
    // Show loading state
    const originalText = dropdownButton.innerHTML;
    dropdownButton.disabled = true;
    dropdownButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Updating...';

    // Mark request as ongoing
    ongoingRequests.add(requestKey);
    
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
            showToast('An error occurred while updating your attendance.', 'error');
            dropdownButton.innerHTML = originalText;
            dropdownButton.disabled = false;
        })
        .finally(() => {
            // Always clear the ongoing request flag
            ongoingRequests.delete(requestKey);
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
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || 'Failed to update RSVP');
            });
        }
        return response.json();
    });
}

/**
 * Update the dropdown state after successful RSVP
 * Works for both button groups and individual dropdowns
 */
function updateDropdownState(elementOrButton, newStatus, eventId) {
    // Find the attendance container
    const attendanceContainer = elementOrButton.closest('.attendance-container');
    if (!attendanceContainer) {
        return;
    }
    
    // Detect button size classes from existing buttons
    const existingButtons = attendanceContainer.querySelectorAll('button');
    let buttonSizeClass = '';
    let dropdownSizeClass = '';
    
    if (existingButtons.length > 0) {
        const firstButton = existingButtons[0];
        if (firstButton.classList.contains('btn-sm')) {
            buttonSizeClass = ' btn-sm';
        } else if (firstButton.classList.contains('btn-lg')) {
            buttonSizeClass = ' btn-lg';
        }
    }
    
    let dropdownHtml = '';
    
    if (newStatus === 'yes') {
        dropdownHtml = `
            <div class="dropdown w-100">
                <button class="btn btn-rsvp-yes dropdown-toggle${buttonSizeClass}" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false">
                    Yes
                </button>
                <ul class="dropdown-menu w-100" aria-labelledby="rsvpDropdown${eventId}">
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
            <div class="dropdown w-100">
                <button class="btn btn-rsvp-no dropdown-toggle${buttonSizeClass}" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false">
                    No
                </button>
                <ul class="dropdown-menu w-100" aria-labelledby="rsvpDropdown${eventId}">
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
            <div class="dropdown w-100">
                <button class="btn btn-rsvp-maybe dropdown-toggle${buttonSizeClass}" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false">
                    Maybe
                </button>
                <ul class="dropdown-menu w-100" aria-labelledby="rsvpDropdown${eventId}">
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
            <div class="dropdown w-100">
                <button class="btn btn-rsvp-waitlisted dropdown-toggle${buttonSizeClass}" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false">
                    Waitlisted
                </button>
                <ul class="dropdown-menu w-100" aria-labelledby="rsvpDropdown${eventId}">
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
            <div class="btn-group w-100" role="group">
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
        
        // Ensure the button has w-100 class
        const dropdown = attendanceContainer.querySelector('.dropdown');
        if (dropdown) {
            const dropdownButton = dropdown.querySelector('button');
            if (dropdownButton) {
                dropdownButton.classList.add('w-100');
            }
        }
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
}
