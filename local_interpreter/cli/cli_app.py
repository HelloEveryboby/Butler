import sys

def start_cli():
    """
    Starts the command-line interface to chat with the interpreter.
    """
    print("Welcome to Local Interpreter. Type 'exit' to quit.")

    while True:
        try:
            user_input = input(">>> ")
            if user_input.lower().strip() == 'exit':
                print("Exiting...")
                break

            # In the future, this input will be sent to the coordinator
            print(f"Echo: {user_input}")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}", file=sys.stderr)
            break

if __name__ == '__main__':
    start_cli()
