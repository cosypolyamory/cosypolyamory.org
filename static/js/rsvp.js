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
    console.log('updateAttendanceStatusFromButton called:', {eventId, status});
    
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
                console.log('RSVP success, calling updateDropdownState with:', {buttonGroup, status: data.status, eventId});
                updateDropdownState(buttonGroup, data.status, eventId);
                updateAttendeeInfo(eventId, data);
                showToast(data.message, 'success');
            } else {
                console.log('RSVP failed:', data.message);
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
    console.log('updateAttendanceStatusFromDropdown called:', {eventId, status});
    
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
                console.log('Dropdown RSVP success, calling updateDropdownState');
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
    .then(response => {
        console.log('Raw response:', response);
        return response.json();
    })
    .then(data => {
        console.log('RSVP response received:', data);
        return data;
    });
}

/**
 * Update the dropdown state after successful RSVP
 * Works for both button groups and individual dropdowns
 */
function updateDropdownState(elementOrButton, newStatus, eventId) {
    console.log('updateDropdownState called with:', {elementOrButton, newStatus, eventId});
    
    // Find the attendance container
    const attendanceContainer = elementOrButton.closest('.attendance-container');
    console.log('Found attendance container:', attendanceContainer);
    
    if (!attendanceContainer) return;
    
    let dropdownHtml = '';
    
    if (newStatus === 'yes') {
        dropdownHtml = `
            <div class="dropdown w-100">
                <button class="btn btn-rsvp-yes dropdown-toggle w-100" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false">
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
                <button class="btn btn-rsvp-no dropdown-toggle w-100" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false">
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
                <button class="btn btn-rsvp-maybe dropdown-toggle w-100" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false">
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
                <button class="btn btn-rsvp-waitlisted dropdown-toggle w-100" type="button" id="rsvpDropdown${eventId}" data-bs-toggle="dropdown" aria-expanded="false">
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
        console.log('Unknown status, restoring to initial state:', newStatus);
        dropdownHtml = `
            <div class="btn-group w-100" role="group">
                <button class="btn btn-rsvp-none attendance-btn" type="button" data-event-id="${eventId}" data-status="yes">
                    Yes
                </button>
                <button class="btn btn-rsvp-none attendance-btn" type="button" data-event-id="${eventId}" data-status="no">
                    No
                </button>
                <button class="btn btn-rsvp-none attendance-btn" type="button" data-event-id="${eventId}" data-status="maybe">
                    Maybe
                </button>
            </div>
        `;
    }
    
    console.log('Setting attendance container HTML to:', dropdownHtml);
    attendanceContainer.innerHTML = dropdownHtml;
    console.log('Attendance container after update:', attendanceContainer.innerHTML);
    
    // Add a brief delay to check if something is overriding our change
    setTimeout(() => {
        console.log('Attendance container after 100ms:', attendanceContainer.innerHTML);
    }, 100);
}

/**
 * Update attendee count and pills after RSVP (events list page specific)
 */
function updateAttendeeInfo(eventId, data) {
    // This function is page-specific and will be overridden by each page
    console.log('updateAttendeeInfo called with:', {eventId, data});
}

/**
 * Show toast notification
 */
function showToast(message, type) {
    // This function is page-specific and will be overridden by each page
    console.log('showToast called:', {message, type});
    alert(message); // Fallback
}