import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_client.dart';
import 'package:mobile/core/network/api_flavor.dart';

void main() {
  test('dev flavor resolves to the local backend base URL', () {
    expect(ApiFlavor.dev.baseUrl, 'http://localhost:8000');
  });

  test('prod flavor resolves to the production base URL', () {
    expect(ApiFlavor.prod.baseUrl, 'https://api.gradient.app');
  });

  test('ApiClient configures dio with the flavor base URL and one interceptor', () {
    final client = ApiClient(flavor: ApiFlavor.staging);
    expect(client.dio.options.baseUrl, 'https://staging-api.gradient.app');
    expect(client.dio.interceptors, hasLength(1));
  });

  test('applyAuthHeader attaches a bearer token when present', () {
    final options = RequestOptions(path: '/health');
    applyAuthHeader(options, 'test-token');
    expect(options.headers['Authorization'], 'Bearer test-token');
  });

  test('applyAuthHeader leaves headers untouched when token is null', () {
    final options = RequestOptions(path: '/health');
    applyAuthHeader(options, null);
    expect(options.headers.containsKey('Authorization'), isFalse);
  });

  test('applyAuthHeader leaves headers untouched when token is empty', () {
    final options = RequestOptions(path: '/health');
    applyAuthHeader(options, '');
    expect(options.headers.containsKey('Authorization'), isFalse);
  });
}
