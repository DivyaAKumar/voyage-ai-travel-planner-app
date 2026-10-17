import uuid
import streamlit as st
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from main import app


st.set_page_config(
    page_title="Voyage — AI Travel Planner",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600&display=swap');

    :root {
        --ink: #20231f;
        --muted: #777d75;
        --paper: #f7f7f2;
        --panel: #ffffff;
        --line: #e5e7df;
        --accent: #526b54;
        --accent-dark: #3e5541;
    }

    .stApp {
        background: var(--paper);
        color: var(--ink);
        font-family: 'DM Sans', sans-serif;
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    .block-container {
        max-width: 1060px;
        padding-top: 1.4rem;
        padding-bottom: 2.5rem;
    }

    .brand {
        font-size: 2.4rem;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--accent);
        margin-bottom: 0.4rem;
    }

    .eyebrow {
        color: var(--accent);
        font-size: 0.75rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        font-weight: 700;
        margin-top: 0;
        margin-bottom: 0.25rem;
    }

    .hero-title {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: clamp(2rem, 4vw, 3.4rem);
        line-height: 1.12;
        letter-spacing: -0.035em;
        color: var(--ink);
        margin: 0;
    }

    .hero-copy {
        max-width: 720px;
        color: var(--muted);
        font-size: 1rem;
        line-height: 1.6;
        margin-top: 0.5rem;
        margin-bottom: 0.6rem;
    }

    .section-label {
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.13em;
        color: var(--muted);
        font-weight: 700;
        margin: 0 0 0.4rem;
    }

    div[data-testid="stTextArea"] textarea {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 14px;
        color: var(--ink);
        padding: 1rem;
        font-size: 1rem;
        line-height: 1.6;
    }

    div[data-testid="stTextArea"] textarea:focus {
        border-color: var(--accent);
        box-shadow: 0 0 0 1px var(--accent);
    }

    div.stButton > button,
    div[data-testid="stFormSubmitButton"] > button {
        background: var(--accent);
        color: white;
        border: 1px solid var(--accent);
        border-radius: 10px;
        padding: 0.7rem 1.15rem;
        font-weight: 600;
        min-height: 2.8rem;
        transition: background 0.2s ease, border 0.2s ease;
    }

    div.stButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        background: var(--accent-dark);
        border-color: var(--accent-dark);
        color: white;
    }

    .suggestion {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 0.95rem 1rem;
        min-height: 90px;
        color: var(--ink);
        font-size: 0.92rem;
        line-height: 1.5;
    }

    .result-heading {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2rem;
        margin: 0.4rem 0 0.2rem;
    }

    .result-subtitle {
        color: var(--muted);
        margin-bottom: 1.2rem;
    }

    div[data-testid="stExpander"] {
    border: 1px solid var(--line);
    border-radius: 12px;
    background: white;
    overflow: hidden;
}

div[data-testid="stExpander"] summary {
    background: #526b54 !important;
    color: #ffffff !important;
}

div[data-testid="stExpander"] summary:hover {
    background: #3e5541 !important;
}

div[data-testid="stExpander"] summary p,
div[data-testid="stExpander"] summary svg {
    color: #ffffff !important;
    fill: #ffffff !important;
}

    hr {
        border-color: var(--line);
        margin: 2rem 0;
    }

    .footnote {
        color: var(--muted);
        font-size: 0.82rem;
        margin-top: 1.5rem;
    }

    [data-testid="stMarkdownContainer"] {
        overflow-wrap: anywhere;
        word-break: normal;
        max-width: 100%;
    }

    div[data-testid="stDownloadButton"] > button {
        background: #526b54;
        color: #ffffff;
        border: 1px solid #526b54;
        border-radius: 10px;
    }

    div[data-testid="stDownloadButton"] > button:hover {
        background: #3e5541;
        color: #ffffff;
        border-color: #3e5541;
    }
    /* Human approval: readable text */
div[data-testid="stRadio"] label,
div[data-testid="stRadio"] label p,
div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
    color: #20231f !important;
}

/* Green radio selection */
div[data-testid="stRadio"] input[type="radio"] {
    accent-color: #526b54 !important;
}

/* Approval feedback input */
div[data-testid="stTextArea"] label,
div[data-testid="stTextArea"] label p {
    color: #20231f !important;
}
    </style>
    """,
    unsafe_allow_html=True,
)


def normalize_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in value
        )
    if isinstance(value, dict):
        return "\n".join(
            f"**{key.replace('_', ' ').title()}:** {val}"
            for key, val in value.items()
        )
    return str(value)


def is_waiting_for_review(result):
    return bool(
        result.get("__interrupt__")
        or (
            result.get("approved") == "pending"
            and result.get("approval_request")
        )
    )


def get_thread_config():
    return {
        "configurable": {
            "thread_id": st.session_state["travel_thread_id"]
        }
    }


def save_graph_result(result):
    st.session_state["travel_state"] = result
    st.session_state["awaiting_review"] = is_waiting_for_review(result)

    if result.get("guardrail_blocked", False):
        st.session_state["travel_result"] = normalize_text(
            result.get("final_response", "")
        )
    elif result.get("final_response"):
        st.session_state["travel_result"] = normalize_text(
            result.get("final_response")
        )
    elif not st.session_state["awaiting_review"]:
        st.session_state["travel_result"] = normalize_text(
            result.get("itinerary", "")
        )


# Header and hero
st.markdown(
    '<div class="brand">VOYAGE</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="eyebrow">Thoughtfully planned, just for you <3</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<h1 class="hero-title">Where would you like to go? </h1>',
    unsafe_allow_html=True,
)

st.markdown(
    '<p class="hero-copy">Tell us what you have in mind. We’ll bring together flight information, '
    'hotel research and a day-by-day itinerary in one considered travel plan.</p>',
    unsafe_allow_html=True,
)


# Describe your trip
with st.form("travel_request_form"):
    st.markdown(
        '<div class="section-label">Describe your trip</div>',
        unsafe_allow_html=True,
    )

    query = st.text_area(
        "Travel request",
        placeholder="For example: Plan a 3-day trip from Raipur to Jaipur for two people, in December, under ₹50,000. Include flights, hotels, food and sightseeing.",
        height=80,
        label_visibility="collapsed",
    )

    submitted = st.form_submit_button(
        "Create my travel plan",
        use_container_width=True,
    )


# A little inspiration
st.markdown(
    '<div class="section-label">A little inspiration</div>',
    unsafe_allow_html=True,
)

suggestions = [
    (
        "Japan, at an easy pace",
        "Plan a 7-day trip to Japan under ₹2 lakh, including flights, hotels and sightseeing.",
    ),
    (
        "A long weekend in Dubai",
        "Plan a 3-day trip to Dubai with flights, hotels and sightseeing under ₹80,000.",
    ),
    (
        "Jaipur in three days",
        "Plan a 3-day trip from Raipur to Jaipur including flights, hotels and sightseeing under ₹1 lakh.",
    ),
]

cols = st.columns(3)

for col, (title, description) in zip(cols, suggestions):
    with col:
        st.markdown(
            f'<div class="suggestion"><strong>{title}</strong><br>'
            f'<span style="color:#777d75">{description}</span></div>',
            unsafe_allow_html=True,
        )


# Generate the travel plan
if submitted:
    if not query.strip():
        st.warning(
            "Describe your trip first, including your destination and any preferences."
        )
    else:
        st.session_state["travel_query"] = query.strip()
        st.session_state.pop("travel_result", None)
        st.session_state.pop("travel_state", None)
        st.session_state["awaiting_review"] = False
        st.session_state["travel_thread_id"] = str(uuid.uuid4())
        st.session_state["review_round"] = 0

        initial_state = {
            "messages": [HumanMessage(content=query.strip())],
            "user_id": "streamlit_user",
            "query": query.strip(),
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "budget_results": "",
            "weather_results": "",
            "trip_constraints": {},
            "selected_agents": [],
            "supervisor_reasoning": "",
            "approval_request": "",
            "human_feedback": "",
            "approved": "pending",
            "llm_calls": 0,
            "final_response": "",
            "guardrail_blocked": False,
        }

        with st.spinner("Putting your travel plan together…"):
            try:
                result = app.invoke(
                    initial_state,
                    config=get_thread_config(),
                )
                save_graph_result(result)

            except Exception:
                st.error(
                    "Your travel plan could not be generated. "
                    "Check the terminal for the full error."
                )


# Load the current graph result
travel_state = st.session_state.get("travel_state", {})


# Trip constraints and specialist results
if travel_state and not travel_state.get("guardrail_blocked", False):
    constraints = travel_state.get("trip_constraints", {})

    if constraints:
        st.markdown("---")
        st.markdown(
            '<div class="section-label">Your trip details</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Review your travel constraints", expanded=False):
            constraint_labels = [
                ("destination", "Destination"),
                ("origin", "Departure city"),
                ("duration", "Trip duration"),
                ("travel_dates", "Travel dates"),
                ("travelers", "Travellers"),
                ("budget", "Budget"),
                ("travel_style", "Travel style"),
            ]

            for key, label in constraint_labels:
                value = constraints.get(key)
                if value:
                    st.markdown(f"**{label}:** {normalize_text(value)}")

            preferences = constraints.get("special_preferences", [])
            if preferences:
                st.markdown("**Special preferences**")
                for preference in preferences:
                    st.markdown(f"- {preference}")

            missing = constraints.get("missing_information", [])
            if missing:
                st.markdown("**Details to clarify**")
                for item in missing:
                    st.markdown(f"- {item}")

        result_sections = [
            ("flight_results", "Flight information"),
            ("hotel_results", "Hotel research"),
            ("weather_results", "Weather information"),
            ("budget_results", "Budget assessment"),
        ]

        available_sections = [
            (key, label, travel_state.get(key))
            for key, label in result_sections
            if travel_state.get(key)
        ]

        if available_sections:
            with st.expander("View specialist research", expanded=False):
                for key, label, value in available_sections:
                    st.markdown(f"**{label}**")
                    st.markdown(normalize_text(value))
                    st.markdown("---")


# Human-in-the-loop review
if st.session_state.get("awaiting_review", False):
    travel_state = st.session_state.get("travel_state", {})
    draft = normalize_text(
        travel_state.get("approval_request")
        or travel_state.get("itinerary", "")
    )

    st.markdown("---")

    st.markdown(
        '<div class="eyebrow">Your trip, considered</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="result-heading">Review your travel plan</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="result-subtitle">Review the draft below before approving it. '
        'You can request changes before the final plan is prepared.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(draft)

    st.markdown("---")

    st.markdown(
        '<div class="section-label">Human approval</div>',
        unsafe_allow_html=True,
    )

    review_round = st.session_state.get("review_round", 0)

    decision = st.radio(
        "Are you happy with this itinerary?",
        options=[
            "Approved by human",
            "Not approved — changes needed",
        ],
        index=None,
        key=f"human_review_decision_{review_round}",
    )

    feedback = ""

    if decision == "Not approved — changes needed":
        feedback = st.text_area(
            "Where does it need changes?",
            placeholder="For example: Reduce the hotel budget, replace the afternoon activities, add more food options, or change the travel schedule.",
            height=120,
            key=f"human_review_feedback_{review_round}",
        )

    if st.button("Submit review", use_container_width=True):
        if decision is None:
            st.warning("Please approve the itinerary or select changes needed.")
        elif decision == "Not approved — changes needed" and not feedback.strip():
            st.warning("Please describe the changes you want before submitting.")
        else:
            resume_decision = {
                "approved": decision == "Approved by human",
                "feedback": feedback.strip(),
            }

            with st.spinner("Processing your review…"):
                try:
                    result = app.invoke(
                        Command(resume=resume_decision),
                        config=get_thread_config(),
                    )

                    save_graph_result(result)

                    st.session_state["review_round"] = review_round + 1

                    st.rerun()

                except Exception:
                    st.error(
                        "Your review could not be processed. "
                        "Check the terminal for the full error."
                    )


# Display the final result
travel_state = st.session_state.get("travel_state", {})

if (
    st.session_state.get("travel_result")
    and not st.session_state.get("awaiting_review", False)
):
    st.markdown("---")

    st.markdown(
        '<div class="eyebrow">Your trip, considered</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="result-heading">Your travel plan</div>',
        unsafe_allow_html=True,
    )

    if travel_state.get("guardrail_blocked", False):
        st.markdown(st.session_state["travel_result"])
    else:
        st.markdown(
            '<div class="result-subtitle">Review the suggestions and verify live prices '
            'and availability before booking.</div>',
            unsafe_allow_html=True,
        )

        st.markdown(st.session_state["travel_result"])

        st.download_button(
            "Download itinerary",
            data=st.session_state["travel_result"],
            file_name="travel_itinerary.md",
            mime="text/markdown",
        )


# Disclaimer
st.markdown(
    '<p class="footnote">Travel details are research suggestions, not reservations. '
    'Verify flight schedules, hotel prices and availability with the provider before booking.</p>',
    unsafe_allow_html=True,
)