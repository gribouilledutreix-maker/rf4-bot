import os

VK_TOKEN = os.environ.get("VK_TOKEN")

def main():
    if not VK_TOKEN:
        print("VK_TOKEN est vide ou absent")
        return

    print("Token utilisé par GitHub :")
    print(VK_TOKEN[:10])

if __name__ == "__main__":
    main()
