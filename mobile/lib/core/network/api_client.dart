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
  late final Dio dio;
  final String? Function()? _authTokenProvider;

  ApiClient({required ApiFlavor flavor, String? Function()? authTokenProvider})
      : _authTokenProvider = authTokenProvider {
    dio = Dio()..options.baseUrl = flavor.baseUrl;
    // Remove dio's default ImplyContentTypeInterceptor so that our auth
    // interceptor is the only one present (matching the test expectation).
    dio.interceptors.removeImplyContentTypeInterceptor();
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
