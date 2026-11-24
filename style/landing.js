const reportLookup = document.querySelector(".report-lookup");

reportLookup.addEventListener("submit", (event) => {
  event.preventDefault();
  const rentalId = document.querySelector("#report-rental-id").value.trim();
  const reportType = document.querySelector("#report-type").value;
  const error = document.querySelector("#lookup-error");
  if (!rentalId) return;

  window.location.assign(
    `/reports/${encodeURIComponent(rentalId)}?report_type=${encodeURIComponent(reportType)}`
  );
  error.textContent = "";
});
