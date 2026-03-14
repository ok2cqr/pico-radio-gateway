<?php
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
$data = json_decode($rawBody, true);

if (!is_array($data)) {
    http_response_code(400);
    echo json_encode(['error' => 'invalid_json']);
    exit;
}

if (!array_key_exists('freq', $data) || !array_key_exists('mode', $data)) {
    http_response_code(400);
    echo json_encode(['error' => 'missing_fields']);
    exit;
}

$data['last_seen'] = time();

file_put_contents(__DIR__.'/radio.json', json_encode($data));
echo json_encode(['status' => 'ok']);
