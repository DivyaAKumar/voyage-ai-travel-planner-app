
import uuid
import streamlit as st
from langchain_core.messages import HumanMessage

# Import the compiled LangGraph app from your existing main.py.
# main.py should only prompt for input inside: if __name__ == "__main__"
from main import app as travel_graph


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

    /* Keep long itinerary text inside the page */
    [data-testid="stMarkdownContainer"] {
        overflow-wrap: anywhere;
        word-break: normal;
        max-width: 100%;
    }

    /* Improve download button contrast */
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
    </style>
    """,
    unsafe_allow_html=True,
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


# Describe your trip — moved above the inspiration section
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


# A little inspiration — moved below the trip form
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

        # Clear the previous result while generating a new one
        st.session_state.pop("travel_result", None)

        with st.spinner("Putting your travel plan together…"):
            try:
                thread_id = str(uuid.uuid4())

                result = travel_graph.invoke(
                    {
                        "messages": [
                            HumanMessage(content=query.strip())
                        ],
                        "query": query.strip(),
                        "flight_results": "",
                        "hotel_results": "",
                        "itinerary": "",
                        "llm_calls": 0,
                    },
                    config={
                        "configurable": {
                            "thread_id": thread_id
                        }
                    },
                )

                messages = result.get("messages", [])
                final_answer = messages[-1].content if messages else ""

                if isinstance(final_answer, list):
                    final_answer = "\n".join(
                        item.get("text", str(item))
                        if isinstance(item, dict)
                        else str(item)
                        for item in final_answer
                    )

                st.session_state["travel_result"] = str(final_answer)
                st.session_state["travel_thread_id"] = thread_id

            except Exception:
                st.error(
                    "Your travel plan could not be generated. "
                    "Check the terminal for the full error."
                )


# Display the generated result
if st.session_state.get("travel_result"):
    st.markdown("---")

    st.markdown(
        '<div class="eyebrow">Your trip, considered</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="result-heading">Your travel plan</div>',
        unsafe_allow_html=True,
    )

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
