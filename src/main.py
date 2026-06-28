from src.agent.loop import Agent


def main() -> None:
    agent = Agent()
    print(agent.step("hello"))


if __name__ == "__main__":
    main()
