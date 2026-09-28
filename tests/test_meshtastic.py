import unittest
from unittest import mock

from spac3ghost.collectors import _mesh_gateway_config, _query_mesh_gateway, meshtastic_status


class MeshGatewayConfigTests(unittest.TestCase):
    def test_defaults_when_no_meshtastic_key(self):
        with mock.patch('spac3ghost.collectors.load_config', return_value={}):
            cfg = _mesh_gateway_config()
        self.assertTrue(cfg['enabled'])
        ids = [g['id'] for g in cfg['gateways']]
        self.assertIn('m2', ids)
        self.assertIn('diy-sx1262', ids)
        by_id = {g['id']: g for g in cfg['gateways']}
        self.assertEqual(by_id['m2']['transport'], 'wifi')
        self.assertEqual(by_id['diy-sx1262']['transport'], 'bluetooth')

    def test_custom_gateways_override_defaults(self):
        custom = {'meshtastic': {'gateways': [
            {'id': 'a', 'label': 'A', 'transport': 'wifi', 'target': '10.0.0.5'},
        ]}}
        with mock.patch('spac3ghost.collectors.load_config', return_value=custom):
            cfg = _mesh_gateway_config()
        self.assertEqual(len(cfg['gateways']), 1)
        self.assertEqual(cfg['gateways'][0]['target'], '10.0.0.5')

    def test_unknown_transport_falls_back_to_serial(self):
        custom = {'meshtastic': {'gateways': [{'id': 'x', 'transport': 'carrier-pigeon'}]}}
        with mock.patch('spac3ghost.collectors.load_config', return_value=custom):
            cfg = _mesh_gateway_config()
        self.assertEqual(cfg['gateways'][0]['transport'], 'serial')


class QueryMeshGatewayTests(unittest.TestCase):
    def test_wifi_gateway_without_target_is_not_configured(self):
        gw = {'id': 'm2', 'label': 'M2', 'transport': 'wifi', 'target': '', 'role': 'gateway'}
        result = _query_mesh_gateway('meshtastic', gw, serials=[])
        self.assertEqual(result['state'], 'not_configured')
        self.assertFalse(result['available'])

    def test_bluetooth_gateway_without_target_is_not_configured(self):
        gw = {'id': 'diy', 'label': 'DIY', 'transport': 'bluetooth', 'target': '', 'role': 'node'}
        result = _query_mesh_gateway('meshtastic', gw, serials=[])
        self.assertEqual(result['state'], 'not_configured')

    def test_serial_gateway_auto_detects_from_candidates(self):
        gw = {'id': 's', 'label': 'Serial', 'transport': 'serial', 'target': '', 'role': 'gateway'}
        serials = [{'path': '/dev/ttyACM0'}]
        with mock.patch('spac3ghost.collectors.run', return_value='Owner: test\n') as run_mock:
            result = _query_mesh_gateway('meshtastic', gw, serials=serials)
        self.assertEqual(result['target'], '/dev/ttyACM0')
        self.assertTrue(result['available'])
        called_args = run_mock.call_args_list[0][0][0]
        self.assertIn('/dev/ttyACM0', called_args)

    def test_missing_cli_reports_cli_missing(self):
        gw = {'id': 'm2', 'label': 'M2', 'transport': 'wifi', 'target': '192.168.1.50', 'role': 'gateway'}
        result = _query_mesh_gateway('', gw, serials=[])
        self.assertEqual(result['state'], 'cli_missing')

    def test_wifi_gateway_uses_host_flag_and_resolved_cli_path(self):
        gw = {'id': 'm2', 'label': 'M2', 'transport': 'wifi', 'target': '192.168.1.50', 'role': 'gateway'}
        with mock.patch('spac3ghost.collectors.run', return_value='') as run_mock:
            result = _query_mesh_gateway('/opt/venv/bin/meshtastic', gw, serials=[])
        self.assertFalse(result['available'])
        self.assertEqual(result['state'], 'unreachable')
        first_call_args = run_mock.call_args_list[0][0][0]
        self.assertEqual(first_call_args[0], '/opt/venv/bin/meshtastic')
        self.assertIn('--host', first_call_args)
        self.assertIn('192.168.1.50', first_call_args)

    def test_bluetooth_gateway_uses_ble_flag(self):
        gw = {'id': 'diy', 'label': 'DIY', 'transport': 'bluetooth', 'target': 'AA:BB:CC:DD:EE:FF', 'role': 'node'}
        with mock.patch('spac3ghost.collectors.run', return_value='Owner: diy\n') as run_mock:
            result = _query_mesh_gateway('meshtastic', gw, serials=[])
        self.assertTrue(result['available'])
        first_call_args = run_mock.call_args_list[0][0][0]
        self.assertIn('--ble', first_call_args)
        self.assertIn('AA:BB:CC:DD:EE:FF', first_call_args)


class MeshtasticStatusTests(unittest.TestCase):
    def test_mixed_wifi_and_bluetooth_gateways_both_report(self):
        cfg = {'meshtastic': {'gateways': [
            {'id': 'm2', 'label': 'M2', 'transport': 'wifi', 'target': '192.168.1.50'},
            {'id': 'diy', 'label': 'DIY', 'transport': 'bluetooth', 'target': 'AA:BB'},
        ]}}
        with mock.patch('spac3ghost.collectors.load_config', return_value=cfg), \
             mock.patch('spac3ghost.collectors.shutil.which', return_value='/usr/bin/meshtastic'), \
             mock.patch('spac3ghost.collectors._mesh_serial_candidates', return_value=[]), \
             mock.patch('spac3ghost.collectors.run', return_value='Owner: node\n'):
            status = meshtastic_status(force=True)
        self.assertEqual(len(status['gateways']), 2)
        transports = {g['transport'] for g in status['gateways']}
        self.assertEqual(transports, {'wifi', 'bluetooth'})
        self.assertTrue(status['available'])
        self.assertIn('2/2', status['summary'])

    def test_disabled_reports_no_gateways(self):
        cfg = {'meshtastic': {'enabled': False}}
        with mock.patch('spac3ghost.collectors.load_config', return_value=cfg):
            status = meshtastic_status(force=True)
        self.assertFalse(status['available'])
        self.assertEqual(status['gateways'], [])


if __name__ == '__main__':
    unittest.main()
