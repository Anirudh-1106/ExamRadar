/// Build-time configuration. Override with --dart-define, for example:
/// flutter build apk --dart-define=API_BASE_URL=https://api.example.in --dart-define=APP_NAME=ExamRadar
class AppConfig {
  static const appName = String.fromEnvironment('APP_NAME', defaultValue: 'ExamRadar');
  static const defaultApiBase = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
  static const version = '0.1.1';
  static const deepLinkScheme = 'examradar';
}
