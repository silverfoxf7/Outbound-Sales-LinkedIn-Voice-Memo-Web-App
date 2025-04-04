// static/script.js
let recorder = null;
let audioChunks = [];
let mediaStream = null;
let isRecording = false;

const startBtn = document.getElementById("start-recording");
const doneBtn = document.getElementById("done-next");
const statusDiv = document.getElementById("status");

// Check if record data exists; if not, disable buttons.
const recordRowElem = document.getElementById("record-row");
if (!recordRowElem) {
  if (startBtn) startBtn.disabled = true;
  if (doneBtn) doneBtn.disabled = true;
}

// Helper: Start recording audio
function startRecording() {
  if (!mediaStream) {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        mediaStream = stream;
        recorder = new MediaRecorder(stream);
        recorder.ondataavailable = e => {
          audioChunks.push(e.data);
        };
        recorder.start();
        isRecording = true;
        statusDiv.innerText = "Recording started.";
      })
      .catch(err => {
        statusDiv.innerText = "Error accessing microphone: " + err;
      });
  } else {
    audioChunks = [];
    recorder.start();
    isRecording = true;
    statusDiv.innerText = "Recording started.";
  }
}

// Helper: Stop recording and return a Promise with the audio blob.
function stopRecording() {
  return new Promise(resolve => {
    recorder.onstop = () => {
      const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
      resolve(audioBlob);
    };
    recorder.stop();
    isRecording = false;
  });
}

// "Start Recording" button click event
if (startBtn) {
  startBtn.addEventListener("click", () => {
    // Open the LinkedIn URL (from the record) in a new tab.
    const linkedinURL = document.getElementById("record-url").innerText;
    window.open(linkedinURL, "_blank");
    startRecording();
    startBtn.disabled = true;
    doneBtn.disabled = false;
  });
}

// "Done & Next" button click event
if (doneBtn) {
  doneBtn.addEventListener("click", async () => {
    if (!isRecording) return;
    statusDiv.innerText = "Processing current recording...";
    const audioBlob = await stopRecording();

    // Prepare form data for the POST request.
    const formData = new FormData();
    formData.append("file", audioBlob, "recording.webm");
    const currentRow = recordRowElem.textContent;
    formData.append("current_row", currentRow);

    fetch("/done", {
      method: "POST",
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.message) {
        // No more records.
        statusDiv.innerText = data.message;
        doneBtn.disabled = true;
        startBtn.disabled = true;
      } else {
        // Update UI with the next record's details.
        document.getElementById("record-url").innerText = data.url;
        document.getElementById("record-company").innerText = data.company;
        document.getElementById("record-connected").innerText = data.connected_on;
        document.getElementById("record-first").innerText = data.first_name;
        document.getElementById("record-last").innerText = data.last_name;
        document.getElementById("record-recording").innerText = data.recording;
        recordRowElem.textContent = data.row;
        statusDiv.innerText = "New record loaded. Recording restarted.";
        // Open the next record's LinkedIn URL.
        window.open(data.url, "_blank");
        startRecording();
      }
    })
    .catch(err => {
      statusDiv.innerText = "Error: " + err;
    });
  });
}
