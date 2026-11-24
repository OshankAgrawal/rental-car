const form = document.querySelector("#pickup-form");
const message = document.querySelector("#message");
const button = form.querySelector("button");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  message.className = "";
  message.textContent = "";
  button.disabled = true;

  try {
    const data = await uploadInspectionForm(form, "/api/pickup-inspections");

    message.className = "success";
    message.textContent = `Pickup analysis completed for ${data.rental_id}.`;
    form.reset();
    const report = document.querySelector("#pickup-report");
    report.querySelector("iframe").src =
      `/reports/${encodeURIComponent(data.rental_id)}?report_type=pickup_inspection`;
    report.hidden = false;
    setInspectionProgress(100, "Pickup inspection report is ready");
  } catch (error) {
    message.className = "error";
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
