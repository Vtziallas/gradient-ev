import 'package:dio/dio.dart';

import 'api_flavor.dart';

/// Attaches a bearer token to [options] if [token] is non-null and
/// non-empty. Pure and independently testable — the dio interceptor below
/// is a thin adapter around this.
void applyAuthHeader(RequestOptions options, String? token) {
  if (token != null && token.isNotEmpty) {
    options.headers['Authorization'] = 'Bearer $token';
  }
}

/// Thin dio wrapper: flavor-scoped base URL + auth-token interceptor.
/// Endpoint methods (API.md) land in feature-level repositories in later
/// plans — this class owns only cross-cutting request config.
class ApiClient {
  final Dio dio;
  final String? Function()? _authTokenProvider;

  ApiClient({required ApiFlavor flavor, String? Function()? authTokenProvider})
      : _authTokenProvider = authTokenProvider,
        dio = Dio(BaseOptions(baseUrl: flavor.baseUrl)) {
    // dio's default ImplyContentTypeInterceptor is left in place so that
    // `dio.post('/x', data: {...})` sends JSON (Content-Type:
    // application/json) rather than being url-encoded — required by the
    // FastAPI backend (future plan). Only our auth interceptor is added
    // here.
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          applyAuthHeader(options, _authTokenProvider?.call());
          handler.next(options);
        },
      ),
    );
  }
}
