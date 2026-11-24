const reportShell = document.querySelector(".report-shell");
const rentalId = reportShell.dataset.rentalId;
const reportType = reportShell.dataset.reportType;
const reportContent = document.querySelector("#report-content");
const reportError = document.querySelector("#report-error");
const reportTitles = {
  pickup_inspection: "Pickup inspection report",
  return_inspection: "Return inspection report",
  final_comparison: "Final comparison report"
};
document.querySelector(".report-header h1").textContent =
  reportTitles[reportType] || "Inspection report";

loadReport();

async function loadReport() {
  try {
    const response = await fetch(
      `/api/reports/${encodeURIComponent(rentalId)}?report_type=${encodeURIComponent(reportType)}`
    );
    const report = await response.json();
    if (!response.ok) throw new Error(report.detail || "Could not load report");
    renderReport(report);
    reportContent.hidden = false;
  } catch (error) {
    reportError.textContent = error.message;
    reportError.hidden = false;
    document.querySelector("#rental-heading").textContent = `Rental ${rentalId}`;
  }
}

function renderReport(report) {
  if (report.report_type === "pickup_inspection") {
    renderPickupReport(report);
    return;
  }
  if (report.report_type === "return_inspection") {
    renderReturnReport(report);
    return;
  }

  const rental = report.rental_information;
  const charges = report.rental_duration_and_charges;
  document.querySelector("#rental-heading").textContent =
    `${rental.rental_id} · ${rental.vehicle_registration}`;

  renderDetails("#rental-information", [
    ["Rental ID", rental.rental_id],
    ["Vehicle registration", rental.vehicle_registration],
    ["Customer name", rental.customer?.name],
    ["Customer phone", rental.customer?.phone]
  ]);
  renderDetails("#rental-charges", [
    ["Pickup date and time", formatDate(charges.pickup_date_and_time)],
    ["Return date and time", formatDate(charges.return_date_and_time)],
    ["Total duration", `${charges.total_rental_duration_hours} billed hour(s)`],
    ["Rate", `INR ${charges.hourly_rental_charge_inr} per hour`],
    ["Rental charge", `INR ${charges.rental_charge_inr}`],
    ["Damage charges", `INR ${charges.damage_charge_inr}`],
    ["Total charge", `INR ${charges.total_charge_inr}`]
  ]);
  document.querySelector("#rental-charges").lastElementChild.classList.add("total-charge");
  renderDamageCharges(charges.damage_charge_items || []);

  const comparison = report.vehicle_damage_comparison;
  renderDamageGroups("#damage-comparison", [
    ["Existing damage at pickup", comparison.existing_damage_at_pickup],
    ["Newly detected damage", comparison.newly_detected_damage],
    ["Potentially worsened damage", comparison.potentially_worsened_damage],
    ["Damage no longer detected", comparison.damage_no_longer_detected]
  ]);

  const summary = report.final_inspection_summary;
  renderInspections([
    ["Pickup inspection", summary.pickup_inspection],
    ["Return inspection", summary.return_inspection]
  ]);
  renderDetails("#damage-summary", [
    ["Existing damage", summary.final_damage_summary.existing_damage_count],
    ["New damage", summary.final_damage_summary.new_damage_count],
    ["Worsened damage", summary.final_damage_summary.worsened_damage_count],
    ["No longer detected", summary.final_damage_summary.resolved_damage_count]
  ]);
}

function renderPickupReport(report) {
  const inspection = report.pickup_inspection;
  renderRentalInformation(report.rental_information);
  renderDetails("#rental-charges", [
    ["Pickup date and time", formatDate(inspection.date_and_time)],
    ["Return date and time", "Pending return inspection"],
    ["Rental duration", "Calculated after return"],
    ["Rental charge", "INR 50 per started hour"]
  ]);
  document.querySelector("#damage-charge-items").replaceChildren();
  renderDamageGroups("#damage-comparison", [
    ["Damage detected at pickup", inspection.frames.map((frame) => ({
      ...frame,
      frame_urls: [frame.frame_url]
    }))]
  ]);
  renderInspections([["Pickup inspection", inspection]]);
  renderDetails("#damage-summary", [
    ["Damage detections at pickup", inspection.detection_count]
  ]);
}

function renderReturnReport(report) {
  const inspection = report.return_inspection;
  renderRentalInformation(report.rental_information);
  renderDetails("#rental-charges", [
    ["Return date and time", formatDate(inspection.date_and_time)],
    ["Rental charge", `INR ${report.rental_charge_inr}`],
    ["Damage charges", `INR ${report.damage_charge_total_inr}`]
  ]);
  const chargeDetails = document.querySelector("#rental-charges");
  const total = document.createElement("div");
  const totalLabel = document.createElement("dt");
  const totalValue = document.createElement("dd");
  totalLabel.textContent = "Total charge";
  totalValue.textContent = `INR ${report.total_charge_inr}`;
  totalValue.className = "total-charge";
  total.append(totalLabel, totalValue);
  chargeDetails.append(total);
  renderDamageCharges(report.damage_charge_items || []);
  renderDamageGroups("#damage-comparison", [
    ["Damage detected at return", inspection.frames.map((frame) => ({
      ...frame,
      frame_urls: [frame.frame_url]
    }))]
  ]);
  renderInspections([["Return inspection", inspection]]);
  renderDetails("#damage-summary", [
    ["Damage detections at return", inspection.detection_count],
    ["Damage charge total", `INR ${report.damage_charge_total_inr}`]
  ]);
}

function renderRentalInformation(rental) {
  document.querySelector("#rental-heading").textContent =
    `${rental.rental_id} · ${rental.vehicle_registration}`;
  renderDetails("#rental-information", [
    ["Rental ID", rental.rental_id],
    ["Vehicle registration", rental.vehicle_registration],
    ["Customer name", rental.customer?.name],
    ["Customer phone", rental.customer?.phone]
  ]);
}

function renderDetails(selector, entries) {
  const list = document.querySelector(selector);
  list.replaceChildren();
  for (const [label, value] of entries) {
    const item = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = value ?? "Not provided";
    item.append(term, detail);
    list.append(item);
  }
}

function renderDamageCharges(items) {
  const container = document.querySelector("#damage-charge-items");
  container.replaceChildren();
  if (!items.length) return;

  const heading = document.createElement("h3");
  heading.textContent = "Employee-entered damage charges";
  const list = document.createElement("ul");
  list.className = "charge-list";
  for (const item of items) {
    const row = document.createElement("li");
    row.textContent = `${item.damage_type}: INR ${item.amount_inr}`;
    list.append(row);
  }
  container.append(heading, list);
}

function renderDamageGroups(selector, groups) {
  const container = document.querySelector(selector);
  container.replaceChildren();
  for (const [title, damages] of groups) {
    const card = document.createElement("article");
    card.className = "damage-card";
    const heading = document.createElement("h3");
    heading.textContent = `${title} (${damages.length})`;
    card.append(heading);

    if (!damages.length) {
      const empty = document.createElement("p");
      empty.textContent = "None";
      card.append(empty);
    }

    for (const damage of damages) {
      const detail = document.createElement("p");
      detail.textContent =
        `${damage.damage_type} · confidence ${(damage.confidence * 100).toFixed(1)}%`;
      card.append(detail);
      appendFrames(card, damage.frame_urls || [damage.frame_url]);
    }
    container.append(card);
  }
}

function renderInspections(inspections) {
  const container = document.querySelector("#inspection-summary");
  container.replaceChildren();
  for (const [title, inspection] of inspections) {
    const card = document.createElement("article");
    card.className = "inspection-card";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const timestamp = document.createElement("p");
    timestamp.textContent = `${formatDate(inspection.date_and_time)} · ${inspection.detection_count} detection(s)`;
    card.append(heading, timestamp);
    appendFrames(
      card,
      (inspection.frames || []).map((frame) => frame.frame_url),
      (inspection.frames || []).map((frame) => frame.damage_type)
    );
    container.append(card);
  }
}

function appendFrames(container, urls, labels = []) {
  const gallery = document.createElement("div");
  gallery.className = "frame-gallery";
  for (const [index, url] of urls.entries()) {
    if (!url) continue;
    const image = document.createElement("img");
    image.src = url;
    image.alt = `Detected ${labels[index] || "vehicle damage"} frame`;
    image.loading = "lazy";
    gallery.append(image);
  }
  if (gallery.childElementCount) container.append(gallery);
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "Not available";
}
