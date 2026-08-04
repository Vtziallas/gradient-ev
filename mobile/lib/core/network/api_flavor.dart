enum ApiFlavor { dev, staging, prod }

extension ApiFlavorBaseUrl on ApiFlavor {
  String get baseUrl {
    switch (this) {
      case ApiFlavor.dev:
        return 'http://localhost:8000';
      case ApiFlavor.staging:
        return 'https://staging-api.gradient.app';
      case ApiFlavor.prod:
        return 'https://api.gradient.app';
    }
  }
}
