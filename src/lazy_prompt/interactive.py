"""Interactive prompt refinement module for lazy_prompt.

This module implements a conversational AI system that engages users in dialogue
to refine their spoken prompts through clarifying questions and iterative feedback.
Users can respond via voice (transcribed) or text, and retake their responses at any time.
"""

from typing import Optional
from openai import OpenAI

from mom_pipeline.live_capture import stream_audio
from mom_pipeline.live_transcribe import transcribe_audio


class InteractiveRefiner:
    """Handles interactive refinement of user prompts through conversational dialogue."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the interactive refiner.
        
        Args:
            api_key: OpenAI API key. If None, uses environment variable.
        """
        self.client = OpenAI(api_key=api_key) if api_key else OpenAI()
        self.conversation_history = []
        
    def start_conversation(self, initial_prompt: str) -> str:
        """Start an interactive refinement conversation.
        
        Args:
            initial_prompt: The user's initial spoken prompt.
            
        Returns:
            The AI's first response asking for clarification.
        """
        system_message = {
            "role": "system",
            "content": (
                "You are an expert prompt refinement assistant. Your goal is to help users "
                "clarify and refine their tasks through conversational dialogue.\n\n"
                "Guidelines:\n"
                "1. Ask 1-2 focused questions at a time to understand the user's goal\n"
                "2. Summarize your understanding and ask for confirmation\n"
                "3. Identify ambiguities, missing context, or constraints\n"
                "4. Suggest improvements or alternative approaches when helpful\n"
                "5. After 2-3 exchanges, propose a refined, detailed prompt\n"
                "6. Be conversational, friendly, and supportive\n\n"
                "When the user confirms the refined prompt is good, respond with:\n"
                "REFINED_PROMPT: [final refined prompt here]"
            )
        }
        
        self.conversation_history = [system_message]
        
        user_message = {
            "role": "user",
            "content": f"I need help refining this task: {initial_prompt}"
        }
        self.conversation_history.append(user_message)
        
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=self.conversation_history,
            temperature=0.7,
        )
        
        ai_response = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": ai_response})
        
        return ai_response
    
    def continue_conversation(self, user_response: str) -> tuple[str, bool]:
        """Continue the refinement conversation.
        
        Args:
            user_response: The user's response to the AI's question.
            
        Returns:
            Tuple of (AI response, is_complete) where is_complete indicates
            if the refinement is done.
        """
        self.conversation_history.append({"role": "user", "content": user_response})
        
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=self.conversation_history,
            temperature=0.7,
        )
        
        ai_response = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": ai_response})
        
        # Check if refinement is complete
        is_complete = "REFINED_PROMPT:" in ai_response
        
        return ai_response, is_complete
    
    def extract_refined_prompt(self, ai_response: str) -> str:
        """Extract the refined prompt from the AI's final response.
        
        Args:
            ai_response: The AI's response containing the refined prompt.
            
        Returns:
            The extracted refined prompt.
        """
        if "REFINED_PROMPT:" in ai_response:
            return ai_response.split("REFINED_PROMPT:", 1)[1].strip()
        return ai_response


def get_user_input_voice_or_text(language: str = "en", api_key: Optional[str] = None) -> Optional[str]:
    """Get user input via voice or text.
    
    Args:
        language: Language for voice transcription.
        api_key: OpenAI API key for transcription.
        
    Returns:
        The user's input as text, or None if cancelled.
    """
    print("\n📝 How would you like to respond?")
    print("  [1] Speak (press Ctrl+C when done)")
    print("  [2] Type")
    print("  [R] Retake (discard and start over)")
    print("  [Q] Quit interactive mode")
    
    choice = input("\nEnter your choice (1/2/R/Q): ").strip().upper()
    
    if choice == "1":
        print("\n🎤 Recording... Press Ctrl+C when done.\n")
        try:
            audio_bytes = stream_audio(duration=None)
            print("\n📝 Transcribing your response...\n")
            
            text, _ = transcribe_audio(audio_bytes, language=language)
            if not text.strip():
                print("❌ No speech detected. Please try again.\n")
                return get_user_input_voice_or_text(language, api_key)
            
            print(f"✓ Transcribed: {text}\n")
            return text
            
        except KeyboardInterrupt:
            print("\n⏸️  Recording cancelled.")
            return get_user_input_voice_or_text(language, api_key)
    
    elif choice == "2":
        user_text = input("Enter your response: ").strip()
        if not user_text:
            print("❌ Empty input. Please try again.\n")
            return get_user_input_voice_or_text(language, api_key)
        return user_text
    
    elif choice == "R":
        return "RETAKE"
    
    elif choice == "Q":
        return "QUIT"
    
    else:
        print("❌ Invalid choice. Please enter 1, 2, R, or Q.\n")
        return get_user_input_voice_or_text(language, api_key)


def interactive_refinement_flow(initial_prompt: str, language: str = "en", api_key: Optional[str] = None) -> str:
    """Run the full interactive refinement flow in the terminal with voice support.
    
    Args:
        initial_prompt: The user's initial spoken prompt.
        language: Language for voice transcription.
        api_key: OpenAI API key.
        
    Returns:
        The final refined prompt.
    """
    refiner = InteractiveRefiner(api_key=api_key)
    
    print("\n" + "="*70)
    print("🤖 Interactive Prompt Refinement")
    print("="*70)
    print("\nYour initial prompt:")
    print(f"  \"{initial_prompt}\"\n")
    
    # Start conversation
    ai_question = refiner.start_conversation(initial_prompt)
    print(f"AI: {ai_question}\n")
    
    # Conversation loop
    max_turns = 5
    turn = 0
    
    while turn < max_turns:
        # Get user input (voice or text)
        user_input = get_user_input_voice_or_text(language=language, api_key=api_key)
        
        if user_input == "RETAKE":
            print("\n" + "="*70)
            print("🔄 Restarting interactive refinement...")
            print("="*70)
            # Restart with fresh conversation
            return interactive_refinement_flow(initial_prompt, language=language, api_key=api_key)
        
        if user_input == "QUIT":
            print("\n\n❌ Interactive refinement cancelled. Returning to original prompt.")
            return initial_prompt
        
        if not user_input:
            continue
        
        # Continue conversation
        ai_response, is_complete = refiner.continue_conversation(user_input)
        print(f"AI: {ai_response}\n")
        
        if is_complete:
            refined = refiner.extract_refined_prompt(ai_response)
            print("="*70)
            print("✅ Refinement Complete!")
            print("="*70)
            print("\nFinal Refined Prompt:")
            print(f"\n{refined}\n")
            print("="*70)
            return refined
        
        turn += 1
    
    # Max turns reached
    print("\n(Refinement process complete after maximum exchanges)\n")
    print("="*70)
    print("Final Prompt (based on conversation):")
    print(f"\n{ai_response}\n")
    print("="*70)
    
    return ai_response

