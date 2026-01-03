"""Interactive prompt refinement module for lazy_prompt.

This module implements an interactive dialogue where the AI asks follow-up questions
to clarify and expand on the user's initial task description, then generates a
comprehensive refined prompt based on the entire conversation.
"""

from typing import Optional
import shutil
import subprocess
from openai import OpenAI

from mom_pipeline.live_capture import stream_audio_auto_stop
from mom_pipeline.live_transcribe import transcribe_audio


def _speak_text(text: str) -> None:
    """Speak text aloud using macOS `say` if available; otherwise, no-op.

    Keeps dependencies minimal while enabling conversational audio playback for AI questions.
    """
    say_cmd = shutil.which("say")
    if not say_cmd or not text.strip():
        return
    try:
        subprocess.run([say_cmd, text], check=False)
    except Exception:
        # Fail silently to avoid interrupting the flow if TTS is unavailable.
        pass


def interactive_dialogue_session(initial_prompt: str, language: str = "en", api_key: Optional[str] = None) -> tuple[list[dict], str]:
    """Run an interactive dialogue with AI asking follow-up questions.
    
    User speaks initial idea → Whisper transcribes → LLM asks clarifying questions
    → User answers via voice → LLM asks more questions → User says "DONE" to finish
    → Returns full conversation for final prompt generation.
    
    Args:
        initial_prompt: The user's initial spoken prompt.
        language: Language for voice transcription.
        api_key: OpenAI API key for transcription and LLM.
        
    Returns:
        Tuple of (conversation_history, combined_transcript) where conversation_history
        is the full chat history and combined_transcript is all user inputs combined.
    """
    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    
    # Remove optional wake phrase "Hey Jarvis" to keep prompts clean
    stripped_initial = initial_prompt
    low = initial_prompt.lower().strip()
    if low.startswith("hey jarvis"):
        stripped_initial = initial_prompt[len(initial_prompt.split(" ", 2)[0]) + len(initial_prompt.split(" ", 2)[1]) + 2 :] if len(initial_prompt.split()) > 2 else ""
        stripped_initial = stripped_initial.strip() or "(no content after wake phrase)"

    print("\n" + "="*70)
    print("🎯 Interactive Dialogue Session")
    print("="*70)
    print("\nYour initial idea:")
    print(f'  "{stripped_initial}"\n')
    print("I'll ask follow-up questions to clarify and expand your requirements.")
    print("Speak naturally - I'll understand your answers.\n")
    print("When done, just say 'DONE' and I'll generate your refined prompt.\n")
    print("="*70 + "\n")
    
    # Initialize conversation history
    conversation_history = [
        {"role": "system", "content": """You are an expert prompt engineer and task analyst speaking with the user.

Your job:
1) Listen to their task, then ask clarifying follow-up questions.
2) Keep the tone conversational and natural (no rigid bullet lists in questions).
3) Ask 1-3 specific, focused questions per turn that dig deeper based on what they already said.
4) Cover objectives, constraints, context, tech preferences, success criteria.
5) When you have enough info, ask: "Are we good to go? I have all I need for a detailed prompt."

Ask in plain sentences, friendly and concise, not formal checklists."""},
        {"role": "user", "content": f"Here's my initial idea:\n\n{stripped_initial}"}
    ]
    
    # Get initial questions from LLM
    print("🤖 AI: Let me ask some clarifying questions...\n")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history,
        temperature=0.7,
    )
    
    ai_questions = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": ai_questions})
    print(f"{ai_questions}\n")
    _speak_text(ai_questions)
    
    # Conversation loop
    turn_number = 1
    all_user_inputs = [initial_prompt]
    
    while True:
        print(f"\n{'='*70}")
        print(f"Turn {turn_number}: Your turn to speak")
        print("="*70)
        print(f"🎤 Recording... (Say 'DONE' when finished, or press Ctrl+C to stop)\n")
        
        try:
            # Capture user's spoken answer
            audio_bytes = stream_audio_auto_stop()
            print("\n📝 Transcribing...\n")
            user_text, _ = transcribe_audio(audio_bytes, language=language)
            
            if not user_text.strip():
                print("❌ No speech detected. Please try again.\n")
                continue
            
            print(f"✓ You said:")
            print(f"  {user_text}\n")
            
            all_user_inputs.append(user_text)
            
            # Check if user said DONE
            user_lower = user_text.lower().strip()
            if any(word in user_lower for word in ["done", "that's it", "that's all", "finished", "complete", "ready", "sleep jarvis", "sleep, jarvis"]):
                print("\n✓ Got it! Generating your detailed prompt...\n")
                conversation_history.append({"role": "user", "content": user_text})
                break
            
            # Add user response to conversation
            conversation_history.append({"role": "user", "content": user_text})
            
            # Get next set of questions from LLM
            print("🤖 AI: Processing your answer...\n")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=conversation_history,
                temperature=0.7,
            )
            
            ai_response = response.choices[0].message.content
            conversation_history.append({"role": "assistant", "content": ai_response})
            print(f"{ai_response}\n")
            _speak_text(ai_response)
            
            turn_number += 1
            
        except KeyboardInterrupt:
            print("\n\n✓ Session stopped. Generating your detailed prompt...\n")
            break
    
    # Combine all user inputs for final analysis
    combined_transcript = " ".join(all_user_inputs)
    
    return conversation_history, combined_transcript


def generate_refined_prompt(conversation_history: list[dict], combined_transcript: str, api_key: Optional[str] = None) -> str:
    """Generate a detailed refined prompt based on the entire conversation.
    
    The LLM uses the full dialogue history to create a comprehensive, structured prompt
    that captures all the user's requirements, goals, constraints, and context.
    
    Args:
        conversation_history: The full chat history between user and AI.
        combined_transcript: All user inputs combined into one string.
        api_key: OpenAI API key.
        
    Returns:
        The final refined prompt.
    """
    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    
    print("="*70)
    print("🧠 Generating Your Refined Prompt")
    print("="*70 + "\n")
    
    # System prompt for final refinement (developer/system-spec focused)
    system_prompt = """You are an expert systems designer and prompt engineer.
Produce a developer-ready system specification prompt from the entire conversation.

Focus on:
- Objective and scope: what must be built, who uses it, in/out of scope.
- Architecture: key components/services, data flow, integrations, deployment target.
- Interfaces & contracts: APIs (endpoints, methods, inputs/outputs, status codes),
  events/queues, CLI/UX flows as applicable.
- Data model: entities, fields, types, relationships, storage choices, indexing.
- Non-functional requirements: performance, scale, latency, availability, durability,
  security, privacy/compliance, observability, rate limits.
- Constraints & assumptions: tech stack preferences/mandates, hosting limits, budgets,
  timelines, regulatory or data residency constraints.
- Error handling & resiliency: retries, backoff, idempotency, fallbacks.
- Testing & acceptance: test strategy, success criteria, sample test cases/fixtures.
- Delivery: artifacts expected (e.g., code, IaC, docs), rollout/migration notes.

Style:
- Concise, professional, and directly usable as a system prompt for an LLM or developer.
- Avoid fluffy language; be specific and actionable.
- Use clear sections with headers and bullet points; include short examples where helpful.
- Keep questions out of the final output; deliver a definitive spec/prompt."""
    
    # Add a final system message to generate the refined prompt
    final_messages = (
        [{"role": "system", "content": system_prompt}] +
        conversation_history +
        [{"role": "user", "content": """Using our entire conversation, produce a developer-ready system prompt/spec.
It should be immediately actionable by an LLM or engineering team to implement.
Include objective, scope, architecture, APIs/contracts, data model, NFRs, constraints,
error handling, testing/acceptance, and delivery expectations. Be concise, precise,
and sectioned for quick execution."""}]
    )
    
    # Call GPT-4o for refinement
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=final_messages,
        temperature=0.7,
    )
    
    refined_prompt = response.choices[0].message.content
    
    return refined_prompt


def interactive_refinement_flow(initial_prompt: str, language: str = "en", api_key: Optional[str] = None) -> str:
    """Run the full interactive dialogue and refinement flow.
    
    Args:
        initial_prompt: The user's initial spoken prompt (used as starting context).
        language: Language for voice transcription.
        api_key: OpenAI API key.
        
    Returns:
        The final refined prompt.
    """
    # Run interactive dialogue
    conversation_history, combined_transcript = interactive_dialogue_session(
        initial_prompt, 
        language=language, 
        api_key=api_key
    )
    
    if not combined_transcript:
        print("❌ No conversation recorded. Returning original prompt.")
        return initial_prompt
    
    # Generate refined prompt based on entire conversation
    refined_prompt = generate_refined_prompt(
        conversation_history,
        combined_transcript,
        api_key=api_key
    )
    
    return refined_prompt



