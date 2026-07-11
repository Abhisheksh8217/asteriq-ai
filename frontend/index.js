// API Configuration
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:5000"
    : "https://asteriq-ai.onrender.com";

// Global State
let mediaRecorder = null;
let recordingChunks = [];
let recordedBlob = null;
let currentSubject = null;
let isSpeaking = false;
let currentAudio = null;

// Session-Specific State (RAG and Concurrency)
let sessionId = null;
let interviewMode = "general"; // "general" or "company"
let targetCompany = "Google";
let filesUploadedCount = 0;
let isJdUploaded = false;

// Auth DOM Elements
const authPanel = document.getElementById("auth-panel");
const appContainer = document.getElementById("app-container");
const landingView = document.getElementById("landing-view");
const generalPrepView = document.getElementById("general-prep-view");
const companyRagView = document.getElementById("company-rag-view");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const switchToRegister = document.getElementById("switch-to-register");
const switchToLogin = document.getElementById("switch-to-login");
const authToast = document.getElementById("auth-toast");
const authToastMessage = document.getElementById("auth-toast-message");
const profileUsername = document.getElementById("profile-username");
const logoutBtn = document.getElementById("logout-btn");

function getAuthHeaders() {
    const token = localStorage.getItem("asteriq_auth_token");
    return token ? { "Authorization": `Bearer ${token}` } : {};
}

// DOM Elements
const welcomeState = document.getElementById("welcomeState");
const interviewState = document.getElementById("interviewState");
const subjectBtns = document.querySelectorAll(".subject-btn");
const subjectBadge = document.getElementById("subjectBadge");
const subjectIcon = document.getElementById("subjectIcon");
const questionNum = document.getElementById("questionNum");
const speakingBubble = document.getElementById("speakingBubble");
const startInterviewBtn = document.getElementById("startInterviewBtn");
const recordBtn = document.getElementById("recordBtn");
const micIcon = document.getElementById("micIcon");
const stopIcon = document.getElementById("stopIcon");
const recordingStatus = document.getElementById("recordingStatus");
const submitBtn = document.getElementById("submitBtn");
const endInterviewBtn = document.getElementById("endInterviewBtn");
const feedbackSection = document.getElementById("feedbackSection");
const getFeedbackArea = document.getElementById("getFeedbackArea");
const getFeedbackBtn = document.getElementById("getFeedbackBtn");
const feedbackContent = document.getElementById("feedbackContent");
const feedbackSubject = document.getElementById("feedbackSubject");
const scoreCircle = document.getElementById("scoreCircle");
const scoreValue = document.getElementById("scoreValue");
const newInterviewBtn = document.getElementById("newInterviewBtn");

// New routing elements
const navGeneralBtn = document.getElementById("nav-general-btn");
const navRagBtn = document.getElementById("nav-rag-btn");
const backToHomeBtn = document.getElementById("back-to-home-btn");
const ragBackToHomeBtn = document.getElementById("rag-back-to-home-btn");
const landingLogoutBtn = document.getElementById("landing-logout-btn");

// Mode & Upload elements
const setupConfigCard = document.getElementById("setupConfigCard");
const activeInterviewArea = document.getElementById("activeInterviewArea");
const configSubjectName = document.getElementById("configSubjectName");

// RAG Upload Elements
const ragSetupCard = document.getElementById("ragSetupCard");
const ragResumeInput = document.getElementById("ragResumeInput");
const ragResumeUploadBtn = document.getElementById("ragResumeUploadBtn");
const ragResumeStatus = document.getElementById("ragResumeStatus");
const ragJdInput = document.getElementById("ragJdInput");
const ragJdUploadBtn = document.getElementById("ragJdUploadBtn");
const ragJdStatus = document.getElementById("ragJdStatus");
const startRagInterviewBtn = document.getElementById("startRagInterviewBtn");
const sessionInfoId = document.getElementById("sessionInfoId");
const sessionUploadCount = document.getElementById("sessionUploadCount");

// Detailed evaluation report elements
const feedbackSummary = document.getElementById("feedbackSummary");
const scoreTechnical = document.getElementById("scoreTechnical");
const barTechnical = document.getElementById("barTechnical");
const scoreCommunication = document.getElementById("scoreCommunication");
const barCommunication = document.getElementById("barCommunication");
const scoreConfidence = document.getElementById("scoreConfidence");
const barConfidence = document.getElementById("barConfidence");
const scoreCompanyFit = document.getElementById("scoreCompanyFit");
const barCompanyFit = document.getElementById("barCompanyFit");
const strengthsList = document.getElementById("strengthsList");
const weaknessesList = document.getElementById("weaknessesList");
const topicsList = document.getElementById("topicsList");
const learningPath = document.getElementById("learningPath");

// Subject Icons Map
const iconMap = {
    "Gen AI": "fas fa-brain text-purple-400",
    "Python": "fab fa-python text-yellow-400",
    "OOP": "fas fa-cubes text-orange-400",
    "DBMS": "fas fa-database text-blue-400",
    "HR Interview": "fas fa-users text-green-400"
};

// ========== UUID GENERATOR ==========
function generateUUID() {
    return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, c =>
        (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
    );
}

function getSessionId() {
    if (!sessionId) {
        sessionId = (typeof crypto.randomUUID === 'function') ? crypto.randomUUID() : generateUUID();
        if (sessionInfoId) sessionInfoId.textContent = sessionId;
        console.log("Session ID generated: " + sessionId);
    }
    return sessionId;
}

// ========== UI STATE FUNCTIONS ==========

function showInterviewPanel(subject) {
    currentSubject = subject;
    
    subjectBtns.forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.subject === subject);
    });
    
    welcomeState.classList.add("hidden");
    interviewState.classList.remove("hidden");
    feedbackSection.classList.add("hidden");
    
    subjectBadge.textContent = subject;
    subjectIcon.className = iconMap[subject] + " text-2xl";
    questionNum.textContent = "1";
    
    // Show configuration setup card, hide active dialogue components
    setupConfigCard.classList.remove("hidden");
    activeInterviewArea.classList.add("hidden");
    
    // Update setup card text
    if (configSubjectName) {
        configSubjectName.textContent = subject;
    }

    speakingBubble.classList.add("hidden");
    startInterviewBtn.classList.remove("hidden");
    recordBtn.classList.remove("hidden");
    recordBtn.disabled = true;
    submitBtn.disabled = true;
    endInterviewBtn.disabled = true;
    recordingStatus.textContent = "Configure and click Start Interview to begin";

}

function updateQuestionNumber(number) {
    questionNum.textContent = number;
}

function showSpeakingBubble() {
    speakingBubble.classList.remove("hidden");
}

function hideSpeakingBubble() {
    speakingBubble.classList.add("hidden");
}

function enableRecording() {
    recordBtn.classList.remove("hidden");
    recordBtn.disabled = false;
    endInterviewBtn.disabled = false;
    recordingStatus.textContent = "Click microphone to record your answer";
}

function disableRecording() {
    recordBtn.disabled = true;
    submitBtn.disabled = true;
    submitBtn.classList.add("hidden");
}

function showFeedbackSection() {
    feedbackSection.classList.remove("hidden");
    getFeedbackArea.classList.remove("hidden");
    feedbackContent.classList.add("hidden");
    endInterviewBtn.disabled = true;
    disableRecording();
    recordingStatus.textContent = "Interview ended";
    hideSpeakingBubble();
}

function displayFeedback(data) {
    feedbackSubject.textContent = currentSubject;
    feedbackSummary.textContent = data.summary || "No overall summary provided.";
    
    // Overall score rendering (circle dash offset)
    const scoreVal = data.overall_score || 0;
    scoreValue.textContent = scoreVal;
    const offset = 301.6 - (scoreVal / 5) * 301.6;
    scoreCircle.style.strokeDashoffset = offset;

    // Sub-dimension score progress bars
    const dimensions = [
        { score: data.technical_score, textEl: scoreTechnical, barEl: barTechnical },
        { score: data.communication_score, textEl: scoreCommunication, barEl: barCommunication },
        { score: data.confidence_score, textEl: scoreConfidence, barEl: barConfidence },
        { score: data.company_fit_score, textEl: scoreCompanyFit, barEl: barCompanyFit }
    ];

    dimensions.forEach(dim => {
        const val = dim.score || 0;
        dim.textEl.textContent = `${val}/5`;
        dim.barEl.style.width = `${(val / 5) * 100}%`;
    });

    // Populate lists
    populateList(strengthsList, data.strengths);
    populateList(weaknessesList, data.weaknesses);
    populateList(topicsList, data.recommended_topics);
    populateList(learningPath, data.learning_path);
    
    getFeedbackArea.classList.add("hidden");
    feedbackContent.classList.remove("hidden");
}

function populateList(element, items) {
    element.innerHTML = "";
    if (items && items.length > 0) {
        items.forEach(item => {
            const li = document.createElement("li");
            li.textContent = item;
            element.appendChild(li);
        });
    } else {
        const li = document.createElement("li");
        li.textContent = "No remarks available.";
        li.className = "text-zinc-500 italic list-none";
        element.appendChild(li);
    }
}

function resetToWelcome() {
    currentSubject = null;
    isSpeaking = false;
    localStorage.removeItem("asteriq_active_session_id");
    localStorage.removeItem("asteriq_active_subject");
    
    welcomeState.classList.remove("hidden");
    interviewState.classList.add("hidden");
    
    recordedBlob = null;
    
    // Reset session states
    sessionId = null;
    filesUploadedCount = 0;
    isJdUploaded = false;
    interviewMode = "general";
    targetCompany = "Google";

    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    
    subjectBtns.forEach((btn) => {
        btn.classList.remove("active");
    });
    
    // Reset mode toggles
    interviewMode = "general";


    welcomeState.classList.remove("hidden");
    interviewState.classList.add("hidden");
    
    recordBtn.classList.remove("bg-red-500", "text-white", "recording-active");
    recordBtn.classList.add("bg-zinc-800/80", "text-gray-400");
    micIcon.classList.remove("hidden");
    stopIcon.classList.add("hidden");
    submitBtn.classList.add("hidden");
    
    speakingBubble.classList.add("hidden");
    
    scoreCircle.style.strokeDashoffset = 301.6;
    getFeedbackBtn.textContent = "Get Feedback";
    getFeedbackBtn.disabled = false;
}

// ========== DOCUMENT UPLOAD ENGINE ==========
async function handleFileUpload(file, docType, statusElement) {
    if (!file) return;

    statusElement.textContent = "Uploading & Ingesting...";
    statusElement.className = "text-yellow-400 text-xs animate-pulse";
    startInterviewBtn.disabled = true;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);
    formData.append("session_id", getSessionId());

    try {
        const response = await fetch(`${API_BASE}/upload-document`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: formData
        });
        const data = await response.json();

        if (data.success && data.ingestion_status === "success") {
            statusElement.textContent = `${file.name} - Ingested successfully (${data.chunks_created} chunks)`;
            statusElement.className = "text-green-400 text-xs font-medium";
            filesUploadedCount++;
            if (sessionUploadCount) sessionUploadCount.textContent = `${filesUploadedCount} file(s) ingested`;
            
            if (docType === "jd") {
                isJdUploaded = true;
                if (startRagInterviewBtn) {
                    startRagInterviewBtn.disabled = false;
                    startRagInterviewBtn.classList.remove("cursor-not-allowed", "from-zinc-600", "to-zinc-700", "text-zinc-300");
                    startRagInterviewBtn.classList.add("from-[#667eea]", "to-[#764ba2]", "text-white", "hover:shadow-purple-500/30");
                    startRagInterviewBtn.textContent = "Start Company Tailored Interview";
                }
            }
            startInterviewBtn.disabled = false;
        } else {
            statusElement.textContent = `Ingestion Failed: ${data.error || "Unknown error"}`;
            statusElement.className = "text-red-400 text-xs font-medium";
        }
    } catch (error) {
        statusElement.textContent = "Network error during upload.";
        statusElement.className = "text-red-400 text-xs font-medium";
        console.error(error);
    } finally {
        startInterviewBtn.disabled = false;
    }
}


// ========== AUDIO FUNCTIONS ==========

function handleAudioStream(response, onComplete) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let mediaSource = new MediaSource();
    let audioUrl = URL.createObjectURL(mediaSource);
    let sourceBuffer;
    let queue = [];
    let isSourceBufferReady = false;

    // Only show speaking bubble when streaming audio
    speakingBubble.classList.remove("hidden");
    isSpeaking = true;
    recordBtn.disabled = false;
    recordingStatus.textContent = "ANZ is speaking... (Click Mic to interrupt and record)";

    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    currentAudio = new Audio(audioUrl);
    currentAudio.play().catch(() => {});

    mediaSource.addEventListener("sourceopen", () => {
        sourceBuffer = mediaSource.addSourceBuffer("audio/mpeg");
        isSourceBufferReady = true;
        while (queue.length > 0 && !sourceBuffer.updating) {
            sourceBuffer.appendBuffer(queue.shift());
        }
        sourceBuffer.addEventListener("updateend", () => {
            if (queue.length > 0 && !sourceBuffer.updating) {
                sourceBuffer.appendBuffer(queue.shift());
            }
        });
    });

    function processChunk({ done, value }) {
        if (done) {
            if (mediaSource.readyState === "open") {
                try {
                    mediaSource.endOfStream();
                } catch (e) {}
            }
            if (onComplete) onComplete();
            return;
        }
        const textChunk = decoder.decode(value, { stream: true });
        textChunk.split("\n").forEach((line) => {
            if (line.trim()) {
                try {
                    const binaryString = atob(line);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    if (isSourceBufferReady && !sourceBuffer.updating) {
                        sourceBuffer.appendBuffer(bytes);
                    } else {
                        queue.push(bytes);
                    }
                } catch (e) {
                    console.error("Base64 decode error:", e);
                }
            }
        });
        reader.read().then(processChunk);
    }

    reader.read().then(processChunk);

    currentAudio.onended = () => {
        isSpeaking = false;
        speakingBubble.classList.add("hidden");
        enableRecording();
        URL.revokeObjectURL(audioUrl);
    };

    currentAudio.onerror = () => {
        isSpeaking = false;
        speakingBubble.classList.add("hidden");
        enableRecording();
        URL.revokeObjectURL(audioUrl);
    };
}


// ========== RECORDING FUNCTIONS ==========

function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
        const options = { mimeType: "audio/webm;codecs=opus" };
        
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            options.mimeType = "audio/webm";
        }
        
        mediaRecorder = new MediaRecorder(stream, options);
        recordingChunks = [];

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                recordingChunks.push(e.data);
            }
        };
        
        mediaRecorder.onstop = () => {
            recordedBlob = new Blob(recordingChunks, { type: "audio/webm" });
            stream.getTracks().forEach((track) => track.stop());
        };

        mediaRecorder.start();
        
        recordBtn.classList.remove("bg-zinc-800/80", "text-gray-400");
        recordBtn.classList.add("bg-red-500", "text-white", "recording-active");
        micIcon.classList.add("hidden");
        stopIcon.classList.remove("hidden");
        recordingStatus.textContent = "Recording... Click again to stop.";
        submitBtn.classList.add("hidden");
        endInterviewBtn.disabled = true;
    }).catch((err) => {
        console.error("Microphone error:", err);
        alert("Cannot access microphone! Please click the lock icon in your browser URL bar and allow Microphone access.");
        recordingStatus.textContent = "Microphone access blocked.";
    });
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        
        recordBtn.classList.remove("bg-red-500", "text-white", "recording-active");
        recordBtn.classList.add("bg-zinc-800/80", "text-gray-400");
        micIcon.classList.remove("hidden");
        stopIcon.classList.add("hidden");
        recordingStatus.textContent = "Answer recorded. Submit when ready.";
        submitBtn.classList.remove("hidden");
        submitBtn.disabled = false;
    }
}


// ========== API FUNCTIONS ==========

async function startInterview() {
    if (interviewMode === "company" && !isJdUploaded) {
        alert("Please upload a Job Description (JD) to start a Company Tailored interview.");
        return;
    }

    // Routing magic: If we are in company mode, hide the RAG setup card and show the active interview area inside general-prep view
    if (interviewMode === "company") {
        companyRagView.classList.add("hidden");
        generalPrepView.classList.remove("hidden");
        welcomeState.classList.add("hidden");
        interviewState.classList.remove("hidden");
        setupConfigCard.classList.add("hidden");
        
        subjectBadge.textContent = "Company Tailored";
        subjectBadge.className = "bg-gradient-to-r from-cyan-500 to-purple-500 text-white px-5 py-2 rounded-full font-semibold shadow-lg";
        subjectIcon.className = "fas fa-building text-2xl text-cyan-400";
    } else {
        setupConfigCard.classList.add("hidden");
    }
    
    activeInterviewArea.classList.remove("hidden");
    recordingStatus.textContent = "Starting session...";

    try {
        const response = await fetch(`${API_BASE}/start-interview`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                ...getAuthHeaders()
            },
            body: JSON.stringify({
                session_id: getSessionId(),
                mode: interviewMode,
                subject: currentSubject,
                company: interviewMode === "company" ? targetCompany : null
            })
        });
        
        // Update session ID if generated/updated by backend
        const backendSessionId = response.headers.get("X-Session-ID");
        if (backendSessionId) {
            sessionId = backendSessionId;
            if (sessionInfoId) sessionInfoId.textContent = sessionId;
        }
        localStorage.setItem("asteriq_active_session_id", getSessionId());

        const contentType = response.headers.get("content-type");
        
        if (contentType && contentType.includes("text/plain")) {
            handleAudioStream(response, () => {
                endInterviewBtn.disabled = false;
            });
        } else {
            const data = await response.json();
            console.log("Question:", data.question);
            enableRecording();
            endInterviewBtn.disabled = false;
        }
    } catch (error) {
        recordingStatus.textContent = "Backend offline or connection error.";
        hideSpeakingBubble();
        setupConfigCard.classList.remove("hidden");
        activeInterviewArea.classList.add("hidden");
    }
}

async function submitAnswer() {
    if (!recordedBlob) return;

    disableRecording();
    recordingStatus.textContent = "Submitting response...";

    const formData = new FormData();
    formData.append("audio", recordedBlob, "answer.webm");
    formData.append("session_id", getSessionId());

    try {
        const response = await fetch(`${API_BASE}/submit-answer?session_id=${getSessionId()}`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: formData
        });
        
        const contentType = response.headers.get("content-type");
        const isComplete = response.headers.get('X-Interview-Complete') === 'true';
        const questionNumber = response.headers.get('X-Question-Number');
        
        if (questionNumber) {
            updateQuestionNumber(questionNumber);
        }
        
        if (contentType && contentType.includes("text/plain")) {
            handleAudioStream(response, () => {
                recordedBlob = null;
                recordingChunks = [];
                
                if (isComplete) {
                    currentAudio.onended = () => {
                        isSpeaking = false;
                        hideSpeakingBubble();
                        showFeedbackSection();
                    };
                } else {
                    endInterviewBtn.disabled = false;
                }
            });
        } else {
            const data = await response.json();
            console.log("Response:", data);
            recordedBlob = null;
            recordingChunks = [];
            
            if (isComplete) {
                showFeedbackSection();
            } else {
                enableRecording();
                endInterviewBtn.disabled = false;
            }
        }
    } catch (error) {
        recordingStatus.textContent = "Connection failed. Please retry submission.";
        hideSpeakingBubble();
        enableRecording();
    }
}

async function endInterview() {
    if (!confirm("End interview and generate feedback now?")) return;

    disableRecording();
    endInterviewBtn.disabled = true;
    recordingStatus.textContent = "Compiling evaluation...";
    
    await getFeedback();
}

async function getFeedback() {
    showFeedbackSection();
    getFeedbackBtn.textContent = "Generating Report...";
    getFeedbackBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/get-feedback`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                ...getAuthHeaders()
            },
            body: JSON.stringify({ session_id: getSessionId() })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayFeedback(data.feedback);
        } else {
            getFeedbackBtn.textContent = "Evaluation Error. Click to retry.";
            getFeedbackBtn.disabled = false;
        }
    } catch (error) {
        getFeedbackBtn.textContent = "Network Error. Click to retry.";
        getFeedbackBtn.disabled = false;
    }
}


// ========== EVENT LISTENERS ==========

// ========== ROUTING LISTENERS ==========
function showLanding() {
    resetToWelcome();
    landingView.classList.remove("hidden");
    generalPrepView.classList.add("hidden");
    companyRagView.classList.add("hidden");
}

navGeneralBtn.addEventListener("click", () => {
    interviewMode = "general";
    landingView.classList.add("hidden");
    generalPrepView.classList.remove("hidden");
});

navRagBtn.addEventListener("click", () => {
    interviewMode = "company";
    landingView.classList.add("hidden");
    companyRagView.classList.remove("hidden");
});

backToHomeBtn.addEventListener("click", showLanding);
ragBackToHomeBtn.addEventListener("click", showLanding);

// Topic Buttons Sidebar click
subjectBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
        if (currentSubject === btn.dataset.subject) return;
        resetToWelcome();
        showInterviewPanel(btn.dataset.subject);
    });
});

// Start Interview Button
startInterviewBtn.addEventListener("click", startInterview);
if (startRagInterviewBtn) {
    startRagInterviewBtn.addEventListener("click", startInterview);
}

// RAG Upload Listeners
if (ragResumeInput) {
    ragResumeInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            ragResumeStatus.textContent = e.target.files[0].name;
            ragResumeUploadBtn.disabled = false;
        }
    });
}
if (ragResumeUploadBtn) {
    ragResumeUploadBtn.addEventListener("click", () => {
        handleFileUpload(ragResumeInput.files[0], "resume", ragResumeStatus);
        ragResumeUploadBtn.disabled = true;
    });
}

if (ragJdInput) {
    ragJdInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            ragJdStatus.textContent = e.target.files[0].name;
            ragJdUploadBtn.disabled = false;
        }
    });
}
if (ragJdUploadBtn) {
    ragJdUploadBtn.addEventListener("click", () => {
        handleFileUpload(ragJdInput.files[0], "jd", ragJdStatus);
        ragJdUploadBtn.disabled = true;
    });
}

recordBtn.addEventListener("click", () => {
    if (recordBtn.disabled) return;
    
    if (isSpeaking && currentAudio) {
        currentAudio.pause();
        isSpeaking = false;
        speakingBubble.classList.add("hidden");
    }
    
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
        startRecording();
    } else {
        stopRecording();
    }
});

submitBtn.addEventListener("click", submitAnswer);
endInterviewBtn.addEventListener("click", endInterview);
getFeedbackBtn.addEventListener("click", getFeedback);
newInterviewBtn.addEventListener("click", resetToWelcome);


// ========== AUTHENTICATION & RESTORATION FLOW ==========

function showAuthError(message) {
    authToastMessage.textContent = message;
    authToast.classList.remove("hidden");
    setTimeout(() => {
        authToast.classList.add("hidden");
    }, 5000);
}

loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;

    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        if (data.success) {
            localStorage.setItem("asteriq_auth_token", data.token);
            localStorage.setItem("asteriq_email", data.email);
            initializeSessionState();
        } else {
            showAuthError(data.error || "Login failed.");
        }
    } catch (err) {
        showAuthError("Connection error. Is the backend running?");
    }
});

registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("register-name").value;
    const email = document.getElementById("register-email").value;
    const password = document.getElementById("register-password").value;

    if (password.length < 6) {
        showAuthError("Password must be at least 6 characters.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password, name })
        });
        const data = await response.json();
        if (data.success) {
            // Auto-login after registration
            const loginRes = await fetch(`${API_BASE}/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password })
            });
            const loginData = await loginRes.json();
            if (loginData.success) {
                localStorage.setItem("asteriq_auth_token", loginData.token);
                localStorage.setItem("asteriq_email", loginData.email);
                initializeSessionState();
            }
        } else {
            showAuthError(data.error || "Registration failed.");
        }
    } catch (err) {
        showAuthError("Connection error.");
    }
});

switchToRegister.addEventListener("click", () => {
    loginForm.classList.add("hidden");
    registerForm.classList.remove("hidden");
    document.getElementById("auth-subtitle").textContent = "Create your account profile";
});

switchToLogin.addEventListener("click", () => {
    registerForm.classList.add("hidden");
    loginForm.classList.remove("hidden");
    document.getElementById("auth-subtitle").textContent = "Sign in to start your tailored AI prep session";
});

logoutBtn.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to log out of your ASTERIQ AI session?")) {
        return;
    }
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    try {
        await fetch(`${API_BASE}/logout`, {
            method: "POST",
            headers: getAuthHeaders()
        });
    } catch (e) {}
    localStorage.clear();
    authPanel.classList.remove("hidden");
    appContainer.classList.add("hidden");
    resetToWelcome();
});

landingLogoutBtn.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to log out of your ASTERIQ AI session?")) {
        return;
    }
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    try {
        await fetch(`${API_BASE}/logout`, {
            method: "POST",
            headers: getAuthHeaders()
        });
    } catch (e) {}
    localStorage.clear();
    authPanel.classList.remove("hidden");
    appContainer.classList.add("hidden");
    resetToWelcome();
});

async function initializeSessionState() {
    const token = localStorage.getItem("asteriq_auth_token");
    const storedEmail = localStorage.getItem("asteriq_email");
    
    if (!token) {
        authPanel.classList.remove("hidden");
        mainLayout.classList.add("hidden");
        return;
    }

    try {
        // Validate active token
        const response = await fetch(`${API_BASE}/validate-token`, {
            headers: getAuthHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            profileUsername.textContent = storedEmail;
            authPanel.classList.add("hidden");
            appContainer.classList.remove("hidden");
            showLanding();
            
            // Restore active session ID if stored
            const savedSessionId = localStorage.getItem("asteriq_active_session_id");
            if (savedSessionId) {
                restoreSession(savedSessionId);
            }
        } else {
            localStorage.clear();
            authPanel.classList.remove("hidden");
            appContainer.classList.add("hidden");
        }
    } catch (err) {
        showAuthError("Connection error connecting to backend.");
    }
}

async function restoreSession(savedSessionId) {
    try {
        const response = await fetch(`${API_BASE}/get-session-state/${savedSessionId}`, {
            headers: getAuthHeaders()
        });
        const data = await response.json();
        
        if (data.success) {
            const session = data.session;
            const history = data.history;
            
            sessionId = session.session_id;
            if (sessionInfoId) sessionInfoId.textContent = sessionId;
            interviewMode = session.mode;
            currentSubject = session.topic;
            targetCompany = session.company || "Google";
            
            // Update active mode tabs
            if (interviewMode === "company") {
                landingView.classList.add("hidden");
                companyRagView.classList.remove("hidden");
            } else {
                landingView.classList.add("hidden");
                generalPrepView.classList.remove("hidden");
            }
            
            // Highlight subject button in sidebar
            subjectBtns.forEach(btn => {
                if (btn.dataset.subject === currentSubject) {
                    btn.classList.add("active");
                } else {
                    btn.classList.remove("active");
                }
            });

            if (session.status === "active") {
                // Show interview interface
                welcomeState.classList.add("hidden");
                interviewState.classList.remove("hidden");
                subjectBadge.textContent = currentSubject;
                if (iconMap[currentSubject]) {
                    subjectIcon.className = iconMap[currentSubject];
                }
                
                // Show RAG file uploads counts
                if (data.files && data.files.length > 0) {
                    filesUploadedCount = data.files.length;
                    if (sessionUploadCount) sessionUploadCount.textContent = `${filesUploadedCount} file(s) ingested`;
                    data.files.forEach(f => {
                        if (f.doc_type === "jd") {
                            isJdUploaded = true;
                            if (jdFileStatus) {
                                jdFileStatus.textContent = `${f.original_name} - Ingested`;
                                jdFileStatus.className = "text-green-400 text-xs font-medium";
                            }
                        } else {
                            if (docsFileStatus) {
                                docsFileStatus.textContent = `${f.original_name} - Ingested`;
                                docsFileStatus.className = "text-green-400 text-xs font-medium";
                            }
                        }
                    });
                }
                
                // Restore history
                if (history && history.length > 0) {
                    const currentQNum = session.question_count;
                    updateQuestionNumber(currentQNum);
                    
                    const latestQuestion = history[history.length - 1].question;
                    recordingStatus.textContent = "Answer when ready.";
                    console.log("Restored active question: " + latestQuestion);
                    
                    enableRecording();
                    endInterviewBtn.disabled = false;
                } else {
                    setupConfigCard.classList.remove("hidden");
                    activeInterviewArea.classList.add("hidden");
                }
            } else if (session.status === "completed") {
                showFeedbackSection();
                await getFeedback();
            }
        } else {
            localStorage.removeItem("asteriq_active_session_id");
        }
    } catch (err) {
        console.error("Error restoring session:", err);
    }
}

// Initialise auth state on load
initializeSessionState();