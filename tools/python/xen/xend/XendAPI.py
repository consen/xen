#============================================================================
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#============================================================================
# Copyright (C) 2006 XenSource Ltd.
#============================================================================

from xen.xend import XendDomain, XendDomainInfo, XendNode
from xen.xend import XendLogging

from xen.xend.XendAuthSessions import instance as auth_manager
from xen.xend.XendAuthSessions import session_required
from xen.xend.XendError import *
from xen.xend.XendClient import ERROR_INVALID_DOMAIN
from xen.xend.XendLogging import log

from xen.xend.XendAPIConstants import *

def xen_api_success(value):
    return {"Status": "Success", "Value": value}
def xen_api_success_void():
    """Return success, but caller expects no return value."""
    return xen_api_success("")
def xen_api_error(error):
    return {"Status": "Error", "ErrorDescription": error}
def xen_api_todo():
    """Temporary method to make sure we track down all the TODOs"""
    return {"Status": "Error", "ErrorDescription": XEND_ERROR_TODO}

def trace(func, api_name = ''):
    """Decorator to trace XMLRPC Xen API methods."""
    if hasattr(func, 'api'):
        api_name = func.api
    def trace_func(self, *args, **kwargs):
        log.debug('%s: %s' % (api_name, args))
        return func(self, *args, **kwargs)
    trace_func.api = api_name
    return trace_func

def valid_host(func):
    """Decorator to verify if host_ref is valid before calling
    method.

    @param func: function with params: (self, session, host_ref)
    @rtype: callable object
    """    
    def check_host_ref(self, session, host_ref, *args, **kwargs):
        xennode = XendNode.instance()
        if type(host_ref) == type(str()) and xennode.is_valid_host(host_ref):
            return func(self, session, host_ref, *args, **kwargs)
        else:
            return {'Status': 'Failure',
                    'ErrorDescription': XEND_ERROR_HOST_INVALID}

    # make sure we keep the 'api' attribute
    if hasattr(func, 'api'):
        check_host_ref.api = func.api
        
    return check_host_ref

def valid_host_cpu(func):
    """Decorator to verify if host_cpu_ref is valid before calling
    method.

    @param func: function with params: (self, session, host_cpu_ref)
    @rtype: callable object
    """    
    def check_host_cpu_ref(self, session, host_cpu_ref, *args, **kwargs):
        xennode = XendNode.instance()
        if type(host_cpu_ref) == type(str()) and \
               xennode.is_valid_cpu(host_cpu_ref):
            return func(self, session, host_cpu_ref, *args, **kwargs)
        else:
            return {'Status': 'Failure',
                    'ErrorDescription': XEND_ERROR_HOST_CPU_INVALID}
        
    # make sure we keep the 'api' attribute
    if hasattr(func, 'api'):
        check_host_cpu_ref.api = func.api
        
    return check_host_cpu_ref

def valid_vm(func):
    """Decorator to verify if vm_ref is valid before calling
    method.

    @param func: function with params: (self, session, vm_ref)
    @rtype: callable object
    """    
    def check_vm_ref(self, session, vm_ref, *args, **kwargs):
        xendom = XendDomain.instance()
        if type(vm_ref) == type(str()) and \
               xendom.is_valid_vm(vm_ref):
            return func(self, session, vm_ref, *args, **kwargs)
        else:
            return {'Status': 'Failure',
                    'ErrorDescription': XEND_ERROR_VM_INVALID}

    # make sure we keep the 'api' attribute
    if hasattr(func, 'api'):
        check_vm_ref.api = func.api
        
    return check_vm_ref

def valid_vbd(func):
    """Decorator to verify if vbd_ref is valid before calling
    method.

    @param func: function with params: (self, session, vbd_ref)
    @rtype: callable object
    """    
    def check_vbd_ref(self, session, vbd_ref, *args, **kwargs):
        xendom = XendDomain.instance()
        if type(vbd_ref) == type(str()) and \
               xendom.is_valid_dev('vbd', vbd_ref):
            return func(self, session, vbd_ref, *args, **kwargs)
        else:
            return {'Status': 'Failure',
                    'ErrorDescription': XEND_ERROR_VBD_INVALID}

    # make sure we keep the 'api' attribute
    if hasattr(func, 'api'):
        check_vbd_ref.api = func.api
        
    return check_vbd_ref

def valid_vif(func):
    """Decorator to verify if vif_ref is valid before calling
    method.

    @param func: function with params: (self, session, vif_ref)
    @rtype: callable object
    """
    def check_vif_ref(self, session, vif_ref, *args, **kwargs):
        xendom = XendDomain.instance()
        if type(vif_ref) == type(str()) and \
               xendom.is_valid_dev('vif', vif_ref):
            return func(self, session, vif_ref, *args, **kwargs)
        else:
            return {'Status': 'Failure',
                    'ErrorDescription': XEND_ERROR_VIF_INVALID}

    # make sure we keep the 'api' attribute
    if hasattr(func, 'api'):
        check_vif_ref.api = func.api
        
    return check_vif_ref

def do_vm_func(fn_name, vm_ref, *args):
    """Helper wrapper func to abstract away from repeative code.

    @param fn_name: function name for XendDomain instance
    @type fn_name: string
    @param vm_ref: vm_ref
    @type vm_ref: string
    @param *args: more arguments
    @type *args: tuple
    """
    xendom = XendDomain.instance()
    fn = getattr(xendom, fn_name)
    return xen_api_success(xendom.do_legacy_api_with_uuid(
        fn, vm_ref, *args))

class XendAPI:
    """Implementation of the Xen-API in Xend. Expects to be
    used via XMLRPCServer.

    All methods that need a valid session are marked with
    a L{XendAuthManager.session_required} decorator that will
    transparently perform the required session authentication.

    We need to support Python <2.4, so we use the old decorator syntax.

    All XMLRPC accessible methods require an 'api' attribute and
    is set to the XMLRPC function name which the method implements.
    """

    def __init__(self):
        """Initialised Xen API wrapper by making sure all functions
        have the correct validation decorators such as L{valid_host}
        and L{session_required}.
        """
        
        classes = {
            'Session': (session_required,),
            'Host': (valid_host, session_required),
            'Host_CPU': (valid_host_cpu, session_required),
            'VM': (valid_vm, session_required),
            'VBD': (valid_vbd, session_required),
            'VIF': (valid_vif, session_required)}
        
        # Cheat methods
        # -------------
        # Methods that have a trivial implementation for all classes.
        # 1. get_by_uuid == getting by ref, so just return uuid.
        
        for cls in classes.keys():
            get_by_uuid = '%s_get_by_uuid' % cls.lower()
            get_uuid = '%s_get_uuid' % cls.lower()            
            setattr(XendAPI, get_by_uuid,
                    lambda s, sess, obj_ref: xen_api_success(obj_ref))
            setattr(XendAPI, get_uuid,
                    lambda s, sess, obj_ref: xen_api_success(obj_ref))

        # 2. get_record is just getting all the attributes, so provide
        #    a fake template implementation.
        # 
        # TODO: ...


        # Wrapping validators around XMLRPC calls
        # ---------------------------------------
        
        for cls, validators in classes.items():
            ro_attrs = getattr(self, '%s_attr_ro' % cls, [])
            rw_attrs = getattr(self, '%s_attr_rw' % cls, [])
            methods  = getattr(self, '%s_methods' % cls, [])
            funcs    = getattr(self, '%s_funcs' % cls, [])

            # wrap validators around readable class attributes
            for attr_name in ro_attrs + rw_attrs + self.Base_attr_ro:
                getter_name = '%s_get_%s' % (cls.lower(), attr_name.lower())
                try:
                    getter = getattr(XendAPI, getter_name)
                    for validator in validators:
                        getter = validator(getter)
                    getter.api = '%s.get_%s' % (cls, attr_name)
                    setattr(XendAPI, getter_name, getter)
                except AttributeError:
                    log.warn("API call: %s not found" % getter_name)

            # wrap validators around writable class attrributes
            for attr_name in rw_attrs + self.Base_attr_rw:
                setter_name = '%s_set_%s' % (cls.lower(), attr_name.lower())
                try:
                    setter = getattr(XendAPI, setter_name)
                    for validator in validators:
                        setter = validator(setter)
                    setter.api = '%s.set_%s' % (cls, attr_name)
                    setattr(XendAPI, setter_name, setter)
                except AttributeError:
                    log.warn("API call: %s not found" % setter_name)

            # wrap validators around methods
            for method_name in methods + self.Base_methods:
                method_full_name = '%s_%s' % (cls.lower(),method_name.lower())
                try:
                    method = getattr(XendAPI, method_full_name)
                    for validator in validators:
                        method = validator(method)
                    method.api = '%s.%s' % (cls, method_name)
                    setattr(XendAPI, method_full_name, method)
                except AttributeError:
                    log.warn('API call: %s not found' % method_full_name)

            # wrap validators around class functions
            for func_name in funcs + self.Base_funcs:
                func_full_name = '%s_%s' % (cls.lower(), func_name.lower())
                try:
                    method = getattr(XendAPI, func_full_name)
                    method = session_required(method)
                    method.api = '%s.%s' % (cls, func_name)
                    setattr(XendAPI, func_full_name, method)
                except AttributeError:
                    log.warn('API call: %s not found' % func_full_name)


    Base_attr_ro = ['uuid']
    Base_attr_rw = []
    Base_methods = ['destroy', 'to_XML', 'get_record']
    Base_funcs   = ['create', 'get_by_uuid', 'get_all']

    # Xen API: Class Session
    # ----------------------------------------------------------------
    # NOTE: Left unwrapped by __init__

    Session_attr_ro = ['this_host', 'this_user']
    Session_methods = ['logout']
    # Session_funcs = ['login_with_password']    

    def session_login_with_password(self, username, password):
        try:
            session = auth_manager().login_with_password(username, password)
            return xen_api_success(session)
        except XendError, e:
            return xen_api_error(XEND_ERROR_AUTHENTICATION_FAILED)
    session_login_with_password.api = 'Session.login_with_password'


    # object methods
    def session_logout(self, session):
        auth_manager().logout(session)
        return xen_api_success_void()
    def session_destroy(self, session):
        return xen_api_error(XEND_ERROR_UNSUPPORTED)
    def session_get_record(self, session):
        record = {'this_host': XendNode.instance().uuid,
                  'this_user': auth_manager().get_user(session)}
        return xen_api_success(record)
    def session_to_xml(self, session):
        return xen_api_todo()

    # attributes (ro)
    def session_get_this_host(self, session):
        return xen_api_success(XendNode.instance().uuid)
    def session_get_this_user(self, session):
        user = auth_manager().get_user(session)
        if user:
            return xen_api_success(user)
        return xen_api_error(XEND_ERROR_SESSION_INVALID)


    # Xen API: Class User
    # ----------------------------------------------------------------
    # TODO: NOT IMPLEMENTED YET

    # Xen API: Class Tasks
    # ----------------------------------------------------------------
    # TODO: NOT IMPLEMENTED YET    

    # Xen API: Class Host
    # ----------------------------------------------------------------    

    Host_attr_ro = ['software_version',
                    'resident_VMs',
                    'host_CPUs']
    
    Host_attr_rw = ['name_label',
                    'name_description']

    Host_methods = ['disable',
                    'enable',
                    'reboot',
                    'shutdown']
    
    Host_funcs = ['get_by_label']

    # attributes
    def host_get_name_label(self, session, host_ref):
        return xen_api_success(XendNode.instance().name)
    def host_set_name_label(self, session, host_ref):
        return xen_api_success(XendNode.instance().name)
    def host_get_name_description(self, session, host_ref):
        return xen_api_success(XendNode.instance().description)    
    def host_set_name_description(self, session, host_ref):
        return xen_api_success(XendNode.instance().description)
    def host_get_software_version(self, session, host_ref):
        return xen_api_success(XendNode.instance().xen_version())
    def host_get_resident_vms(self, session, host_ref):
        return xen_api_success(XendDomain.instance().get_domain_refs())
    def host_get_host_cpus(self, session, host_ref):
        return xen_api_success(XendNode.instance().get_host_cpu_refs())

    # object methods
    def host_destroy(self, session, host_ref):
        return xen_api_error(XEND_ERROR_UNSUPPORTED)    
    def host_disable(self, session, host_ref):
        XendDomain.instance().set_allow_new_domains(False)
        return xen_api_success_void()
    def host_enable(self, session, host_ref):
        XendDomain.instance().set_allow_new_domains(True)
        return xen_api_success_void()
    def host_reboot(self, session, host_ref):
        if not XendDomain.instance().allow_new_domains():
            return xen_api_error(XEND_ERROR_HOST_RUNNING)
        return xen_api_error(XEND_ERROR_UNSUPPORTED)
    def host_shutdown(self, session, host_ref):
        if not XendDomain.instance().allow_new_domains():
            return xen_api_error(XEND_ERROR_HOST_RUNNING)
        return xen_api_error(XEND_ERROR_UNSUPPORTED)        
    def host_get_record(self, session, host_ref):
        node = XendNode.instance()
        dom = XendDomain.instance()
        record = {'name_label': node.name,
                  'name_description': '',
                  'software_version': node.xen_version(),
                  'resident_VMs': dom.get_domain_refs(),
                  'host_CPUs': node.get_host_cpu_refs()}
        return xen_api_success(record)

    # class methods
    def host_get_all(self, session):
        return xen_api_success((XendNode.instance().uuid,))
    def host_create(self, session, struct):
        return xen_api_error(XEND_ERROR_UNSUPPORTED)

    # Xen API: Class Host_CPU
    # ----------------------------------------------------------------

    Host_CPU_attr_ro = ['host',
                        'number',
                        'features',
                        'utilisation']

    # attributes
    def host_cpu_get_uuid(self, session, host_cpu_ref):
        uuid = XendNode.instance().get_host_cpu_uuid(host_cpu_ref)
        return xen_api_success(uuid)
    def host_cpu_get_host(self, session, host_cpu_ref):
        return xen_api_success(XendNode.instance().uuid)
    def host_cpu_get_features(self, session, host_cpu_ref):
        features = XendNode.instance().get_host_cpu_features(host_cpu_ref)
        return xen_api_success(features)
    def host_cpu_get_utilisation(self, session, host_cpu_ref):
        util = XendNode.instance().get_host_cpu_load(host_cpu_ref)
        return xen_api_success(util)
    def host_cpu_get_number(self, session, host_cpu_ref):
        num = XendNode.instance().get_host_cpu_number(host_cpu_ref)
        return xen_api_success(num)

    # object methods
    def host_cpu_destroy(self, session, host_cpu_ref):
        return xen_api_error(XEND_ERROR_UNSUPPORTED)
    def host_cpu_get_record(self, session, host_cpu_ref):
        node = XendNode.instance()
        record = {'uuid': host_cpu_ref,
                  'host': node.uuid,
                  'number': node.get_host_cpu_number(host_cpu_ref),
                  'features': node.get_host_cpu_features(host_cpu_ref),
                  'utilisation': node.get_host_cpu_load(host_cpu_ref)}
        return xen_api_success(record)
    def host_cpu_to_xml(self, session, host_cpu_ref):
        return xen_api_todo()

    # class methods
    def host_cpu_get_all(self, session):
        return xen_api_success(XendNode.instance().get_host_cpu_refs())
    def host_cpu_create(self, session, struct):
        return xen_api_error(XEND_ERROR_UNSUPPORTED)


    # Xen API: Class Network
    # ----------------------------------------------------------------
    # TODO: NOT IMPLEMENTED

    Network_attr_ro = ['VIFs']
    Network_attr_rw = ['name_label',
                       'name_description',
                       'NIC',
                       'VLAN',
                       'default_gateway',
                       'default_netmask']

    # Xen API: Class VM
    # ----------------------------------------------------------------        

    VM_attr_ro = ['power_state',
                  'resident_on',
                  'memory_actual',
                  'memory_static_max',                  
                  'memory_static_min',
                  'VCPUs_number',
                  'VCPUs_utilisation',
                  'VCPUs_features_required',
                  'VCPUs_can_use',
                  'VIFs',
                  'VBDs',
                  'TPM_instance',
                  'TPM_backend',
                  'PCI_bus',
                  'tools_version',
                  ]
                  
    VM_attr_rw = ['name_label',
                  'name_description',
                  'user_version',
                  'is_a_template',
                  'memory_dynamic_max',
                  'memory_dynamic_min',
                  'VCPUs_policy',
                  'VCPUs_params',
                  'VCPUs_features_force_on',
                  'VCPUS_features_force_off',
                  'actions_after_shutdown',
                  'actions_after_reboot',
                  'actions_after_suspend',
                  'actions_after_crash',
                  'bios_boot',
                  'platform_std_VGA',
                  'platform_serial',
                  'platform_localtime',
                  'platform_clock_offset',
                  'platform_enable_audio',
                  'builder',
                  'boot_method',
                  'kernel_kernel',
                  'kernel_initrd',
                  'kernel_args',
                  'grub_cmdline',
                  'other_config']

    VM_methods = ['clone',
                  'start',
                  'pause',
                  'unpause',
                  'clean_shutdown',
                  'clean_reboot',
                  'hard_shutdown',
                  'hard_reboot',
                  'suspend',
                  'resume']
    
    VM_funcs  = ['get_by_label']

    # parameters required for _create()
    VM_attr_inst = [
        'name_label',
        'name_description',
        'user_version',
        'is_a_template',
        'memory_static_max',
        'memory_dynamic_max',
        'memory_dynamic_min',
        'memory_static_min',
        'VCPUs_policy',
        'VCPUs_params',
        'VCPUs_features_required',
        'VCPUs_features_can_use',
        'VCPUs_features_force_on',
        'VCPUs_features_force_off',
        'actions_after_shutdown',
        'actions_after_reboot',
        'actions_after_suspend',
        'actions_after_crash',
        'TPM_instance',
        'TPM_backend',
        'bios_boot',
        'platform_std_VGA',
        'platform_serial',
        'platform_localtime',
        'platform_clock_offset',
        'platform_enable_audio',
        'builder',
        'boot_method',
        'kernel_kernel',
        'kernel_initrd',
        'kernel_args',
        'grub_cmdline',
        'PCI_bus',
        'other_config']
        
    # attributes (ro)
    def vm_get_power_state(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success(dom.state)
    
    def vm_get_resident_on(self, session, vm_ref):
        return xen_api_success(XendNode.instance().uuid)
    
    def vm_get_memory_actual(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo() # unsupported by xc
    
    def vm_get_memory_static_max(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success(dom.get_memory_static_max())
    
    def vm_get_memory_static_min(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success(dom.get_memory_static_min())
    
    def vm_get_vcpus_number(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success(dom.getVCpuCount())
    
    def vm_get_vcpus_utilisation(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success(dom.get_vcpus_util())
    
    def vm_get_vcpus_features_required(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo() # unsupported by xc
    
    def vm_get_vcpus_can_use(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo() # unsupported by xc
    
    def vm_get_vifs(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success(dom.get_vifs())
    
    def vm_get_vbds(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success(dom.get_vbds())
    
    def vm_get_tpm_instance(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo() # unsupported by xc
    
    def vm_get_tpm_backend(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo() # unsupported by xc
    
    def vm_get_pci_bus(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo() # unsupported by xc
    
    def vm_get_tools_version(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()

    # attributes (rw)
    def vm_get_name_label(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success(dom.getName())
    
    def vm_get_name_description(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_user_version(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_is_a_template(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_memory_dynamic_max(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()

    def vm_get_memory_dynamic_min(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()    
    
    def vm_get_vcpus_policy(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo() # need to access scheduler
    
    def vm_get_vcpus_params(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo() # need access to scheduler
    
    def vm_get_vcpus_features_force_on(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_vcpus_features_force_off(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_actions_after_shutdown(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_actions_after_reboot(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_actions_after_suspend(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_actions_after_crash(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_bios_boot(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_platform_std_vga(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_platform_serial(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_platform_localtime(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_platform_clock_offset(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_platform_enable_audio(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_builder(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_get_boot_method(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_kernel_kernel(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_kernel_initrd(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_kernel_args(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_grub_cmdline(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success('')
    
    def vm_get_other_config(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_todo()
    
    def vm_set_name_label(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_name_description(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_user_version(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_is_a_template(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_memory_dynamic_max(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_memory_dynamic_min(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_vcpus_policy(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_vcpus_params(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_vcpus_features_force_on(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_vcpus_features_force_off(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_actions_after_shutdown(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_actions_after_reboot(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_actions_after_suspend(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_actions_after_crash(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_bios_boot(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_platform_std_vga(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_platform_serial(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_platform_localtime(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_platform_clock_offset(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_platform_enable_audio(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_builder(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_boot_method(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_kernel_kernel(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_kernel_initrd(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_kernel_args(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_grub_cmdline(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    def vm_set_other_config(self, session, vm_ref):
        dom = XendDomain.instance().get_vm_by_uuid(vm_ref)
        return xen_api_success_void()
    
    # class methods
    def vm_get_all(self, session):
        refs = [d.get_uuid() for d in XendDomain.instance().list()]
        return xen_api_success(refs)
    def vm_get_by_label(self, session, label):
        xendom = XendDomain.instance()
        dom = xendom.domain_lookup_nr(label)
        if dom:
            return xen_api_success(dom.get_uuid())
        return xen_api_error(XEND_ERROR_VM_INVALID)
    def vm_create(self, session, vm_struct):
        xendom = XendDomain.instance()
        domuuid = xendom.create_domain(vm_struct)
        return xen_api_success(domuuid)
    
    # object methods
    def vm_to_xml(self, session, vm_ref):
        return xen_api_todo()
    
    def vm_get_record(self, session, vm_ref):
        xendom = XendDomain.instance()
        xeninfo = xendom.get_vm_by_uuid(vm_ref)
        if not xeninfo:
            return xen_api_error(XEND_ERROR_VM_INVALID)
        
        record = {
            'uuid': xeninfo.get_uuid(),
            'power_state': xeninfo.get_power_state(),
            'name_label': xeninfo.getName(),
            'name_description': xeninfo.getName(),
            'user_version': 1,
            'is_a_template': False,
            'resident_on': XendNode.instance().uuid,
            'memory_static_min': xeninfo.get_memory_static_min(),
            'memory_static_max': xeninfo.get_memory_static_max(),
            'memory_dynamic_min': xeninfo.get_memory_static_min(),
            'memory_dynamic_max': xeninfo.get_memory_static_max(),
            'memory_actual': xeninfo.get_memory_static_min(),
            'vcpus_policy': xeninfo.get_vcpus_policy(),
            'vcpus_params': xeninfo.get_vcpus_params(),
            'vcpus_number': xeninfo.getVCpuCount(),
            'vcpus_utilisation': xeninfo.get_vcpus_util(),
            'vcpus_features_required': [],
            'vcpus_features_can_use': [],
            'vcpus_features_force_on': [],
            'vcpus_features_force_off': [],
            'actions_after_shutdown': xeninfo.get_on_shutdown(),
            'actions_after_reboot': xeninfo.get_on_reboot(),
            'actions_after_suspend': xeninfo.get_on_suspend(),
            'actions_after_crash': xeninfo.get_on_crash(),
            'vifs': xeninfo.get_vifs(),
            'vbds': xeninfo.get_vbds(),
            'tpm_instance': xeninfo.get_tpm_instance(),
            'tpm_backend': xeninfo.get_tpm_backend(),
            'bios_boot': xeninfo.get_bios_boot(),
            'platform_std_vga': xeninfo.get_platform_std_vga(),
            'platform_serial': xeninfo.get_platform_serial(),
            'platform_localtime': xeninfo.get_platform_localtime(),
            'platform_clock_offset': xeninfo.get_platform_clock_offset(),
            'platform_enable_audio': xeninfo.get_platform_enable_audio(),
            'builder': xeninfo.get_builder(),
            'boot_method': xeninfo.get_boot_method(),
            'kernel_kernel': xeninfo.get_kernel_image(),
            'kernel_initrd': xeninfo.get_kernel_initrd(),
            'kernel_args': xeninfo.get_kernel_args(),
            'grub_cmdline': xeninfo.get_grub_cmdline(),
            'pci_bus': xeninfo.get_pci_bus(),
            'tools_version': xeninfo.get_tools_version(),
            'otherconfig': xeninfo.get_other_config()
        }
        return xen_api_success(record)

    def vm_clean_reboot(self, session, vm_ref):
        xendom = XendDomain.instance()
        xeninfo = xendom.get_vm_by_uuid(vm_ref)
        xeninfo.shutdown("reboot")
        return xen_api_success_void()
    def vm_clean_shutdown(self, session, vm_ref):
        xendom = XendDomain.instance()
        xeninfo = xendom.get_vm_by_uuid(vm_ref)
        xeninfo.shutdown("poweroff")
        return xen_api_success_void()
    def vm_clone(self, session, vm_ref):
        return xen_api_error(XEND_ERROR_UNSUPPORTED)
    def vm_destroy(self, session, vm_ref):
        return do_vm_func("domain_delete", vm_ref)
    def vm_hard_reboot(self, session, vm_ref):
        return xen_api_error(XEND_ERROR_UNSUPPORTED)    
    def vm_hard_shutdown(self, session, vm_ref):
        return do_vm_func("domain_destroy", vm_ref)    
    def vm_pause(self, session, vm_ref):
        return do_vm_func("domain_pause", vm_ref)
    def vm_resume(self, session, vm_ref, start_paused):
        return do_vm_func("domain_resume", vm_ref)    
    def vm_start(self, session, vm_ref):
        return do_vm_func("domain_start", vm_ref)
    def vm_suspend(self, session, vm_ref):
        return do_vm_func("domain_suspend", vm_ref)    
    def vm_unpause(self, session, vm_ref):
        return do_vm_func("domain_unpause", vm_ref)

    # Xen API: Class VDI
    # ----------------------------------------------------------------
    # TODO: NOT IMPLEMENTED.

    # Xen API: Class VBD
    # ----------------------------------------------------------------

    VBD_attr_ro = ['image',
                   'IO_bandwidth_incoming_kbs',
                   'IO_bandwidth_outgoing_kbs']
    VBD_attr_rw = ['VM',
                   'VDI',
                   'device',
                   'mode',
                   'driver']

    VBD_attr_inst = VBD_attr_rw + ['image']

    # object methods
    def vbd_get_record(self, session, vbd_ref):
        xendom = XendDomain.instance()
        return xen_api_success(xendom.get_dev_by_uuid('vbd', vbd_ref,
                                                      'driver'))

    # class methods
    def vbd_create(self, session, vbd_struct):
        xendom = XendDomain.instance()
        if xendom.is_valid_vm(vbd_struct['VM']):
            dom = xendom.get_vm_by_uuid(vbd_struct['VM'])
            try:
                vbd_ref = dom.create_vbd(vbd_struct)
                return xen_api_success(vbd_ref)
            except XendError:
                return xen_api_error(XEND_ERROR_TODO)
        else:
            return xen_api_error(XEND_ERROR_DOMAIN_INVALID)


    # attributes (rw)
    def vbd_get_vm(self, session, vbd_ref):
        xendom = XendDomain.instance()
        return xen_api_success(xendom.get_dev_by_uuid('vbd', vbd_ref, 'VM'))
    def vbd_get_vdi(self, session, vbd_ref):
        return xen_api_error(XEND_ERROR_UNSUPPORTED)
    def vbd_get_device(self, session, vbd_ref):
        xendom = XendDomain.instance()
        return xen_api_success(xendom.get_dev_by_uuid('vbd', vbd_ref,
                                                      'device'))
    def vbd_get_mode(self, session, vbd_ref):
        xendom = XendDomain.instance()
        return xen_api_success(xendom.get_dev_by_uuid('vbd', vbd_ref,
                                                      'mode'))
    def vbd_get_driver(self, session, vbd_ref):
        xendom = XendDomain.instance()
        return xen_api_success(xendom.get_dev_by_uuid('vbd', vbd_ref,
                                                      'driver'))

    # Xen API: Class VIF
    # ----------------------------------------------------------------

    VIF_attr_ro = ['network_read_kbs',
                   'network_write_kbs',
                   'IO_bandwidth_incoming_kbs',
                   'IO_bandwidth_outgoing_kbs']
    VIF_attr_rw = ['name',
                   'type',
                   'device',
                   'network',
                   'VM',
                   'MAC',
                   'MTU']

    VIF_attr_inst = VIF_attr_rw

    # class methods
    def vif_create(self, session, vif_struct):
        xendom = XendDomain.instance()
        if xendom.is_valid_vm(vif_struct['VM']):
            dom = xendom.get_vm_by_uuid(vif_struct['VM'])
            try:
                vif_ref = dom.create_vif(vif_struct)
                return xen_api_success(vif_ref)
            except XendError:
                return xen_api_error(XEND_ERROR_TODO)
        else:
            return xen_api_error(XEND_ERROR_DOMAIN_INVALID)


    # Xen API: Class SR
    # ----------------------------------------------------------------
    # NOT IMPLEMENTED


    
