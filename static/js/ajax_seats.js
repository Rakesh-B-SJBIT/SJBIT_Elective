/**
 * SJBIT Elective System — Real-Time Seat Availability (AJAX)
 * CO5 Implementation: fetch-based seat counter without page refresh
 */

function updateSeatWidget(courseId) {
  fetch('/api/seats/' + courseId + '/')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      // Update fill bars
      var fillElements = document.querySelectorAll('.cc-seats-fill.seat-fill-' + courseId);
      for (var i = 0; i < fillElements.length; i++) {
        fillElements[i].style.width = data.pct + '%';
      }
      // Update available text
      var availableElements = document.querySelectorAll('.seat-available-' + courseId);
      for (var j = 0; j < availableElements.length; j++) {
        availableElements[j].textContent = data.available + ' seats left';
        availableElements[j].className = availableElements[j].className.replace(/text-\w+/, '');
        if (data.label === 'full')        availableElements[j].classList.add('text-danger');
        else if (data.label === 'almost_full') availableElements[j].classList.add('text-warning');
        else                              availableElements[j].classList.add('text-success');
      }
    })
    .catch(function() {/* silently fail */});
}

function updateBulkSeats(courseIds) {
  if (!courseIds || !courseIds.length) return;
  var ids = courseIds.join(',');
  fetch('/api/seats/?ids=' + ids)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.courses) return;
      var courses = data.courses;
      for (var id in courses) {
        if (courses.hasOwnProperty(id)) {
          var d = courses[id];
          var fillElements = document.querySelectorAll('.cc-seats-fill.seat-fill-' + id);
          for (var i = 0; i < fillElements.length; i++) {
            fillElements[i].style.width = d.pct + '%';
          }
          var availableElements = document.querySelectorAll('.seat-available-' + id);
          for (var j = 0; j < availableElements.length; j++) {
            availableElements[j].textContent = d.available + ' seats left';
            availableElements[j].className = availableElements[j].className.replace(/text-\w+/g, '').trim();
            if (d.label === 'full')        availableElements[j].classList.add('text-danger');
            else if (d.label === 'almost_full') availableElements[j].classList.add('text-warning');
            else                           availableElements[j].classList.add('text-success');
          }
        }
      }
    })
    .catch(function() {});
}
