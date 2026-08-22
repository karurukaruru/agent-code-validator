from calculator import average


def main() -> None:
    raw_values = input("Enter comma-separated numbers: ")
    values = [float(value) for value in raw_values.split(",")]
    print(f"Average: {average(values)}")


if __name__ == "__main__":
    main()

