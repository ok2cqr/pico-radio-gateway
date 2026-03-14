<?php
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

$data = file_get_contents(__DIR__.'/radio.json');
if (false === $data) {
    echo '{"freq":"0","mode":"","last_seen":0}';
    exit;
}

echo $data;
