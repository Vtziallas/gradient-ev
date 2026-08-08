import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_client.dart';
import 'package:mobile/core/network/api_flavor.dart';

/// Captures the fully-resolved [RequestOptions] dio hands to the transport
/// layer — i.e. after all interceptors (including the default
/// ImplyContentTypeInterceptor) have run — without making a real request.
class _CapturingAdapter implements HttpClientAdapter {
  RequestOptions? lastOptions;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    lastOptions = options;
    final body = utf8.encode(jsonEncode({'ok': true}));
    return ResponseBody.fromBytes(body, 200, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  test('dev flavor resolves to the local backend base URL', () {
    expect(ApiFlavor.dev.baseUrl, 'http://localhost:8000');
  });

  test('prod flavor resolves to the production base URL', () {
    expect(ApiFlavor.prod.baseUrl, 'https://api.gradient.app');
  });

  test('ApiClient configures dio with the flavor base URL and installs one auth interceptor', () {
    final client = ApiClient(flavor: ApiFlavor.staging);
    expect(client.dio.options.baseUrl, 'https://staging-api.gradient.app');
    expect(client.dio.interceptors.whereType<InterceptorsWrapper>(), hasLength(1));
  });

  test('ApiClient keeps dio\'s default content-type-implying interceptor alongside ours', () {
    final client = ApiClient(flavor: ApiFlavor.staging);
    // Our auth interceptor plus dio's built-in ImplyContentTypeInterceptor
    // (not part of dio's public API surface, so asserted by count/behavior
    // rather than by type — see the request-encoding test below for the
    // behavioral proof).
    expect(client.dio.interceptors, hasLength(2));
  });

  test('a Map body posted through ApiClient is sent as JSON, not url-encoded', () async {
    final client = ApiClient(flavor: ApiFlavor.staging);
    final adapter = _CapturingAdapter();
    client.dio.httpClientAdapter = adapter;

    await client.dio.post('/x', data: {'a': 1});

    expect(adapter.lastOptions, isNotNull);
    expect(adapter.lastOptions!.contentType, contains(Headers.jsonContentType));
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
