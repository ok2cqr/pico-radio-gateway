<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

$apiKey = 'change-me';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'method_not_allowed']);
    exit;
}

$authHeader = '';
if (isset($_SERVER['HTTP_AUTHORIZATION'])) {
    $authHeader = $_SERVER['HTTP_AUTHORIZATION'];
} elseif (isset($_SERVER['REDIRECT_HTTP_AUTHORIZATION'])) {
    $authHeader = $_SERVER['REDIRECT_HTTP_AUTHORIZATION'];
}

$expectedAuth = 'Bearer '.$apiKey;
if ($authHeader !== $expectedAuth) {
    http_response_code(401);
    echo json_encode(['error' => 'unauthorized']);
    exit;
}

$rawBody = file_get_contents('php://input');
if ($rawBody === false) {
    http_response_code(400);
    echo json_encode(['error' => 'read_failed']);
    exit;
}

try {
    $payload = json_decode($rawBody, false, 512, JSON_THROW_ON_ERROR);
} catch (JsonException $e) {
    error_log('radio-upload invalid JSON: '.$e->getMessage());
    http_response_code(400);
    echo json_encode(['error' => 'invalid_json']);
    exit;
}

if (!$payload instanceof stdClass) {
    error_log('radio-upload rejected non-object payload: '.$rawBody);
    http_response_code(400);
    echo json_encode(['error' => 'invalid_payload_shape']);
    exit;
}

if (!property_exists($payload, 'freq') || !property_exists($payload, 'mode')) {
    http_response_code(400);
    echo json_encode(['error' => 'missing_fields']);
    exit;
}

$data = [
    'freq' => (string) $payload->freq,
    'mode' => (string) $payload->mode,
];
$data['last_seen'] = time();

try {
    $json = json_encode($data, JSON_THROW_ON_ERROR);
} catch (JsonException $e) {
    error_log('radio-upload encode failed: '.$e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'encode_failed']);
    exit;
}

if (file_put_contents(__DIR__.'/radio.json', $json, LOCK_EX) === false) {
    error_log('radio-upload write failed for '.__DIR__.'/radio.json');
    http_response_code(500);
    echo json_encode(['error' => 'write_failed']);
    exit;
}

echo json_encode(['status' => 'ok']);
