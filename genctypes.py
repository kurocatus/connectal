#!/usr/bin/python
import os, sys
import AST
import newrt
import syntax

creatorTemplate = '''
%(namespace)s%(className)s *%(namespace)s%(className)s::create%(className)s(const char *instanceName)
{
    UshwInstance *p = ushwOpen(instanceName);
    %(namespace)s%(className)s *instance = new %(namespace)s%(className)s(p);
    return instance;
}

'''
constructorTemplate='''
%(namespace)s%(className)s::%(className)s(UshwInstance *p)
%(initializers)s{
    this->p = p;
}
%(namespace)s%(className)s::~%(className)s()
{
    p->close();
}

'''

methodTemplate='''
struct %(className)s%(methodName)sMSG : public UshwMessage
{
%(paramStructDeclarations)s
};

void %(namespace)s%(className)s::%(methodName)s ( %(paramDeclarations)s )
{
    %(className)s%(methodName)sMSG msg;
    msg.argsize = sizeof(msg)-sizeof(UshwMessage);
    msg.resultsize = 0;
%(paramSetters)s
    p->sendMessage(&msg);
};
'''

def indent(f, indentation):
    for i in xrange(indentation):
        f.write(' ')

class MethodMixin:
    def collectTypes(self):
        result = [self.type_decl]
        result.append(AST.Type('Tuple#', self.params))
        return result
    def emitCDeclaration(self, f, indentation=0, parentClassName='', namespace=''):
        indent(f, indentation)
        f.write('void %s ( ' % cName(self.name))
        print parentClassName, self.name
        for p in self.params:
            print p
            print cName(p)
            print
        f.write(', '.join([cName(p.type) for p in self.params]))
        f.write(' );\n');
    def emitCImplementation(self, f, className, namespace):
        paramDeclarations = [ '%s %s' % (p.type.cName(), p.name) for p in self.params]
        paramStructDeclarations = [ '%s %s;\n' % (p.type.cName(), p.name) for p in self.params]
        paramSetters = [ 'msg.%s = %s;\n' % (p.name, p.name) for p in self.params]
        substs = {
            'namespace': namespace,
            'className': className,
            'methodName': cName(self.name),
            'paramDeclarations': ', '.join(paramDeclarations),
            'paramStructDeclarations': ''.join(paramStructDeclarations),
            'paramSetters': ''.join(paramSetters)
            }
        f.write(methodTemplate % substs)

class StructMemberMixin:
    def emitCDeclaration(self, f, indentation=0, parentClassName='', namespace=''):
        indent(f, indentation)
        f.write('%s %s' % (self.type.cName(), self.tag))
        if self.type.isBitField():
            f.write(' : %d' % self.type.bitWidth())
        f.write(';\n')

class StructMixin:
    def collectTypes(self):
        result = [self]
        result.append(self.elements)
        return result
    def emitCDeclaration(self, f, indentation=0, parentClassName='', namespace=''):
        indent(f, indentation)
        if (indentation == 0):
            f.write('typedef ')
        f.write('struct %s {\n' % self.name.cName())
        for e in self.elements:
            e.emitCDeclaration(f, indentation+4)
        indent(f, indentation)
        f.write('}')
        if (indentation == 0):
            f.write(' %s;' % self.name.cName())
        f.write('\n')
    def emitCImplementation(self, f, className='', namespace=''):
        pass

class EnumElementMixin:
    def cName(self):
        return self.name

class EnumMixin:
    def collectTypes(self):
        result = [self]
        return result
    def emitCDeclaration(self, f, indentation=0, parentClassName='', namespace=''):
        indent(f, indentation)
        if (indentation == 0):
            f.write('typedef ')
        f.write('enum %s { ' % self.name.cName())
        indent(f, indentation)
        f.write(', '.join([e.cName() for e in self.elements]))
        indent(f, indentation)
        f.write(' }')
        if (indentation == 0):
            f.write(' %s;' % self.name.cName())
        f.write('\n')
    def emitCImplementation(self, f, className='', namespace=''):
        pass

class InterfaceMixin:
    def collectTypes(self):
        result = [d.collectTypes() for d in self.decls]
        return result
    def emitCDeclaration(self, f, indentation=0, parentClassName='', namespace=''):
        self.toplevel = (indentation == 0)
        name = cName(self.name)
        indent(f, indentation)
        f.write('class %s {\n' % name)
        indent(f, indentation)
        f.write('public:\n')
        if (not indentation):
            indent(f, indentation+4)
            f.write('static %(name)s *create%(name)s(const char *instanceName);\n'
                    % {'name': name})
        for d in self.decls:
            d.emitCDeclaration(f, indentation + 4, name, namespace)
        indent(f, indentation)
        f.write('private:\n')
        indent(f, indentation+4)
        f.write('%(name)s(UshwInstance *);\n' % {'name': name})
        indent(f, indentation+4)
        f.write('~%(name)s();\n' % {'name': name})
        indent(f, indentation+4)
        f.write('UshwInstance *p;\n')
        if parentClassName:
            indent(f, indentation+4)
            f.write('friend class %s%s;\n' % (namespace, parentClassName))
        indent(f, indentation)
        f.write('}')
        if self.subinterfacename:
            f.write(' %s' % self.subinterfacename)
        f.write(';\n');
    def emitCImplementation(self, f, parentClassName='', namespace=''):
        if parentClassName:
            namespace = '%s%s::' % (namespace, parentClassName)
        className = cName(self.name)
        self.emitConstructorImplementation(f, className, namespace)
        for d in self.decls:
            d.emitCImplementation(f, className, namespace)
    def emitConstructorImplementation(self, f, className, namespace):
        substitutions = {'namespace': namespace,
                         'className': className,
                         'initializers': ''}
        subinterfaces = []
        for d in self.decls:
            print type(d), d
            if d.__class__ == AST.Interface:
                subinterfaces.append(d.subinterfacename)
        if subinterfaces:
            substitutions['initializers'] = (': %s\n'
                                             % ', '.join([ '%s(p)' % i for i in subinterfaces]))
        if self.toplevel:
            f.write(creatorTemplate % substitutions)
        f.write(constructorTemplate % substitutions)

class ParamMixin:
    def cName(self):
        return self.name

class TypeMixin:
    def cName(self):
        cid = self.name
        cid = cid.replace(' ', '')
        if cid == 'Bit#':
            return 'unsigned int'
        cid = cid.replace('#', '_')
        if self.params:
            name = '%sL_%s_P' % (cid, '_'.join([cName(t) for t in self.params if t]))
        else:
            name = cid
        return name
    def isBitField(self):
        return self.name == 'Bit#'
    def bitWidth(self):
        if self.name == 'Bit#':
            return int(self.params[0])
        else:
            return 0
    
def cName(x):
    if type(x) == str:
        x = x.replace(' ', '')
        return x.replace('#', '_')
    else:
        return x.cName()

AST.Method.__bases__ += (MethodMixin,)
AST.StructMember.__bases__ += (StructMemberMixin,)
AST.Struct.__bases__ += (StructMixin,)
AST.EnumElement.__bases__ += (EnumElementMixin,)
AST.Enum.__bases__ += (EnumMixin,)
AST.Type.__bases__ += (TypeMixin,)
AST.Param.__bases__ += (ParamMixin,)
AST.Interface.__bases__ += (InterfaceMixin,)

if __name__=='__main__':
    newrt.printtrace = True
    s = open(sys.argv[1]).read() + '\n'
    s1 = syntax.parse('goal', s)
    print s1
    if len(sys.argv) > 2:
        h = open('%s.h' % sys.argv[2], 'w')
        cpp = open('%s.cpp' % sys.argv[2], 'w')
        cpp.write('#include "ushw.h"\n')
        cpp.write('#include "%s.h"\n' % sys.argv[2])
    else:
        h = sys.stdout
        cpp = sys.stdout
    for v in syntax.globaldecls:
        print v.name
        print v.collectTypes()
        v.emitCDeclaration(h)
        v.emitCImplementation(cpp)
