const form = document.querySelector("#return-form");
const message = document.querySelector("#message");
const button = form.querySelector("button");
const review = document.querySelector("#damage-review");
const reviewButton = document.querySelector("#next-damage");
const amountInput = document.querySelector("#damage-amount");
let inspectionId;
let chargeCandidates = [];
let currentDamageIndex = 0;
const charges = [];

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  message.className = "";
  message.textContent = "";
  button.disabled = true;

  try {
    const data = await uploadInspectionForm(form, "/api/return-inspections");

    if (!data.charge_required) {
      showReturnReport(data);
      return;
    }

    inspectionId = data.inspection_id;
    chargeCandidates = data.charge_candidates;
    form.hidden = true;
    review.hidden = false;
    showCurrentDamage();
  } catch (error) {
    message.className = "error";
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

function showCurrentDamage() {
  const damage = chargeCandidates[currentDamageIndex];
  document.querySelector("#damage-progress").textContent =
    `Damage ${currentDamageIndex + 1} of ${chargeCandidates.length}`;
  const frames = document.querySelector("#damage-frames");
  frames.replaceChildren();
  for (const frameUrl of damage.frame_urls) {
    const image = document.createElement("img");
    image.className = "damage-frame";
    image.src = frameUrl;
    image.alt = `AI-detected ${damage.damage_type} damage`;
    image.loading = "lazy";
    frames.append(image);
  }
  document.querySelector("#damage-title").textContent = damage.damage_type;
  document.querySelector("#damage-reason").textContent =
    damage.reason === "newly_detected"
      ? "New damage detected at return."
      : "Potentially worsened damage compared with pickup.";
  amountInput.value = "";
  reviewButton.textContent =
    currentDamageIndex === chargeCandidates.length - 1
      ? "Save charge and generate report"
      : "Save charge and continue";
  setInspectionProgress(
    (currentDamageIndex / chargeCandidates.length) * 100,
    `Damage charges entered: ${currentDamageIndex} of ${chargeCandidates.length}`
  );
}

reviewButton.addEventListener("click", async () => {
  if (!amountInput.reportValidity()) return;

  charges.push({
    detection_id: chargeCandidates[currentDamageIndex].detection_id,
    amount: amountInput.value
  });
  currentDamageIndex += 1;
  setInspectionProgress(
    (currentDamageIndex / chargeCandidates.length) * 100,
    `Damage charges entered: ${currentDamageIndex} of ${chargeCandidates.length}`
  );
  if (currentDamageIndex < chargeCandidates.length) {
    showCurrentDamage();
    return;
  }

  reviewButton.disabled = true;
  setInspectionProgress(0, "Saving damage charges and generating final report");
  try {
    const response = await fetch(`/api/return-inspections/${inspectionId}/charges`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ charges })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not generate final report");
    showReturnReport(data);
  } catch (error) {
    charges.pop();
    currentDamageIndex -= 1;
    showCurrentDamage();
    message.className = "error";
    message.textContent = error.message;
  } finally {
    reviewButton.disabled = false;
  }
});

function showReturnReport(data) {
  form.hidden = true;
  review.hidden = true;
  const report = document.querySelector("#return-report");
  report.querySelector("iframe").src =
    `/reports/${encodeURIComponent(data.rental_id)}?report_type=return_inspection`;
  report.hidden = false;
  setInspectionProgress(100, "Final comparison report is ready");
  message.className = "success";
  message.textContent = `Final report generated. Total charge: INR ${data.total_charge}.`;
}
