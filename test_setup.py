"""
Simple setup verification script
Run this to check if your environment is configured correctly
"""
import sys
import os


def check_python_version():
    """Check Python version"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"✓ Python version: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python version: {version.major}.{version.minor}.{version.micro} (requires 3.11+)")
        return False


def check_dependencies():
    """Check if key dependencies are installed"""
    deps = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "openai",
        "supabase",
        "pgvector",
        "pypdf",
        "httpx"
    ]

    all_ok = True
    for dep in deps:
        try:
            __import__(dep)
            print(f"✓ {dep} installed")
        except ImportError:
            print(f"✗ {dep} not installed")
            all_ok = False

    return all_ok


def check_env_file():
    """Check if .env file exists"""
    if os.path.exists(".env"):
        print("✓ .env file exists")
        return True
    else:
        print("✗ .env file not found (copy from .env.example)")
        return False


def check_env_variables():
    """Check if required environment variables are set"""
    from dotenv import load_dotenv
    load_dotenv()

    required_vars = [
        "OPENAI_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_KEY"
    ]

    all_ok = True
    for var in required_vars:
        value = os.getenv(var)
        if value and value != f"your_{var.lower()}_here":
            print(f"✓ {var} is set")
        else:
            print(f"✗ {var} not set or uses placeholder value")
            all_ok = False

    return all_ok


def check_config():
    """Check if config loads correctly"""
    try:
        from app.core.config import settings
        print(f"✓ Configuration loaded successfully")
        print(f"  - Embedding model: {settings.embedding_model}")
        print(f"  - Chat model: {settings.chat_model}")
        print(f"  - Environment: {settings.environment}")
        return True
    except Exception as e:
        print(f"✗ Configuration failed to load: {str(e)}")
        return False


def check_directories():
    """Check if required directories exist"""
    dirs = ["app", "mcp_server", "sql", "uploads"]
    all_ok = True

    for dir_name in dirs:
        if os.path.isdir(dir_name):
            print(f"✓ {dir_name}/ directory exists")
        else:
            print(f"✗ {dir_name}/ directory not found")
            all_ok = False

    return all_ok


def main():
    """Run all checks"""
    print("=" * 60)
    print("Chat PDF - Setup Verification")
    print("=" * 60)
    print()

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Environment File", check_env_file),
        ("Environment Variables", check_env_variables),
        ("Configuration", check_config),
        ("Project Structure", check_directories),
    ]

    results = []
    for name, check_func in checks:
        print(f"\n{name}:")
        print("-" * 40)
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"✗ Error running check: {str(e)}")
            results.append(False)

    print()
    print("=" * 60)
    if all(results):
        print("✓ All checks passed! You're ready to go.")
        print()
        print("Next steps:")
        print("1. Run the API server: ./run_api.sh")
        print("2. Visit http://localhost:8000/docs")
        print("3. Upload a PDF and test chat")
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        print()
        print("Common solutions:")
        print("- Install dependencies: pip install -r requirements.txt")
        print("- Copy .env.example to .env and fill in your API keys")
        print("- Ensure you're in the project root directory")
    print("=" * 60)


if __name__ == "__main__":
    main()
