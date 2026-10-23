import os
from pathlib import Path
from unittest.mock import patch
import pytest
from app.system.host_stats import host_snapshot
from app.stack import compose
from app.ui import HTML


def test_host_snapshot_shape():
    data=host_snapshot()
    assert data['cpu_cores']>=1
    assert data['memory_total_bytes']>0
    assert data['root_disk_total_bytes']>=data['root_disk_free_bytes']>=0
    assert isinstance(data['network_interfaces'],dict)


def test_compose_update_invalid_preserves_existing(tmp_path):
    folder=tmp_path/'demo';folder.mkdir();f=folder/'compose.yaml';f.write_text('services:\n  web:\n    image: nginx:alpine\n')
    with patch.object(compose,'STACK_ROOT',tmp_path),patch.object(compose,'run_docker',side_effect=compose.ComposeFailure('operation')):
        with pytest.raises(compose.ComposeFailure):compose.update_stack('demo','services:\n  bad: 1234\n',True)
        assert 'nginx:alpine' in f.read_text()
        assert not (folder/'compose.pending.yaml').exists()


def test_compose_update_valid_and_read(tmp_path):
    folder=tmp_path/'demo';folder.mkdir();f=folder/'compose.yaml';f.write_text('services:\n  web:\n    image: nginx:alpine\n')
    new='services:\n  web:\n    image: httpd:alpine\n'
    with patch.object(compose,'STACK_ROOT',tmp_path),patch.object(compose,'run_docker') as mock:
        assert compose.update_stack('demo',new,True)['deployed'] is False
        assert compose.read_stack('demo')['yaml']==new
        assert mock.called


def test_compose_update_ack_required(tmp_path):
    with pytest.raises(PermissionError):compose.update_stack('demo','services: yes',False)


def test_ui_integrated_views():
    for token in ['v0.7.0','hostMetrics','refreshHostMetrics','Edit YAML','Validate & save changes']:
        assert token in HTML
