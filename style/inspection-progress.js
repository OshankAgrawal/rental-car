function setInspectionProgress(percent, detail) {
  const progressBar = document.querySelector("#progress-bar");
  const progressMessage = document.querySelector("#progress-message");
  if (!progressBar || !progressMessage) return;
  progressBar.value = Math.max(0, Math.min(100, percent));
  progressMessage.textContent = detail;
}

function uploadInspectionForm(form, endpoint) {
  const rentalId = new FormData(form).get("rental_id").trim();
  const xhr = new XMLHttpRequest();
  let uploadComplete = false;
  let requestSettled = false;
  let pollInFlight = false;

  const pollTimer = window.setInterval(async () => {
    if (!uploadComplete || requestSettled || pollInFlight) return;
    pollInFlight = true;
    try {
      const response = await fetch(
        `/api/inspections/${encodeURIComponent(rentalId)}/progress`
      );
      if (response.ok) {
        const state = await response.json();
        if (state.stage !== "waiting") {
          setInspectionProgress(state.percent, state.detail);
        }
      }
    } catch (error) {
      const progressBar = document.querySelector("#progress-bar");
      setInspectionProgress(
        progressBar ? progressBar.value : 0,
        `Progress update unavailable: ${error.message}`
      );
    } finally {
      pollInFlight = false;
    }
  }, 500);

  return new Promise((resolve, reject) => {
    xhr.open("POST", endpoint);
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        const percent = Math.floor((event.loaded / event.total) * 100);
        setInspectionProgress(percent, `Uploading video: ${percent}%`);
      }
    });
    xhr.upload.addEventListener("load", () => {
      uploadComplete = true;
      setInspectionProgress(0, "Video uploaded; waiting for AI analysis");
    });
    xhr.addEventListener("load", () => {
      requestSettled = true;
      window.clearInterval(pollTimer);
      let data;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        reject(new Error("The server returned an invalid response"));
        return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        setInspectionProgress(0, data.detail || "Video processing failed");
        reject(new Error(data.detail || "Video upload failed"));
        return;
      }
      setInspectionProgress(100, "Video analysis complete");
      resolve(data);
    });
    xhr.addEventListener("error", () => {
      requestSettled = true;
      window.clearInterval(pollTimer);
      reject(new Error("Network error while uploading the video"));
    });
    xhr.addEventListener("abort", () => {
      requestSettled = true;
      window.clearInterval(pollTimer);
      reject(new Error("Video upload was cancelled"));
    });
    xhr.send(new FormData(form));
  });
}
