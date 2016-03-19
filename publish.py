import os, sys, re
import config, bs, boilerplate, parser_microsyntax
from StringIO import StringIO
from anolislib import generator, utils
import html5lib
from html5lib.constants import spaceCharacters
from html5lib import treebuilders
from lxml import etree

def invoked_incorrectly():
    specs = config.load_config().keys()
    sys.stderr.write("Usage: python {0!s} [{1!s}]\n".format(sys.argv[0], '|'.join(specs)))
    exit()

spaceCharacters = "".join(spaceCharacters)
spacesRegex = re.compile("[{0!s}]+".format(spaceCharacters))
non_ifragment = re.compile("[^A-Za-z0-9._~!$&'()*+,;=:@/\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF\U00010000-\U0001FFFD\U00020000-\U0002FFFD\U00030000-\U0003FFFD\U00040000-\U0004FFFD\U00050000-\U0005FFFD\U00060000-\U0006FFFD\U00070000-\U0007FFFD\U00080000-\U0008FFFD\U00090000-\U0009FFFD\U000A0000-\U000AFFFD\U000B0000-\U000BFFFD\U000C0000-\U000CFFFD\U000D0000-\U000DFFFD\U000E1000-\U000EFFFD]+")
def generateID(source, el):
    source = source.strip(spaceCharacters).lower()

    if source == "":
        source = "generatedID"
    else:
        source = non_ifragment.sub("-", source).strip("-")
        if source == "":
            source = "generatedID"

    # Initally set the id to the source
    id = source

    i = 0
    while utils.getElementById(el.getroottree().getroot(), id) is not None:
        id = "{0!s}-{1:d}".format(source, i)
        i += 1
    utils.ids[el.getroottree().getroot()][id] = el
    return id

def main(spec, spec_dir, branch="master"):
    conf = None
    try:
        conf = config.load_config()[spec]
    except KeyError:
        invoked_incorrectly()

    if 'select' in conf:
        select = conf['select']
    else:
        select = spec

    try:
        if not spec_dir:
            if conf.get("bareOutput", False):
                spec_dir = conf["output"]
            else:
                spec_dir = os.path.join(conf["output"], spec)
    except KeyError:
        sys.stderr.write("error: Must specify output directory for {0!s}! \
Check default-config.json.\n".format(spec))
        exit()

    cur_dir = os.path.abspath(os.path.dirname(__file__))
    os.chdir(conf["path"])

    print "parsing"
    source = open('source')
    after_microsyntax = StringIO()
    parser_microsyntax.main(source, after_microsyntax)
    after_microsyntax.seek(0)
    succint = StringIO()
    bs.main(after_microsyntax, succint)

    succint.seek(0)
    filtered = StringIO()
    if spec == "microdata":
        md_content = succint.read()
        md_content = re.sub('<h2 id="iana">IANA considerations</h2>',
                            '<!--BOILERPLATE microdata-extra-section--><h2 id="iana">IANA considerations</h2>',
                            md_content)
        succint = StringIO()
        succint.write(md_content)
        succint.seek(0)
    
    try:
        boilerplate.main(succint, filtered, select, branch)
    except IOError:
        sys.stderr.write("error: Problem loading boilerplate for {0!s}. \
Are you on the correct branch?\n".format(spec))
        exit()
    succint.close()

    # See http://hg.gsnedders.com/anolis/file/tip/anolis
    opts = {
      'allow_duplicate_dfns': True,
      'disable': None,
      'escape_lt_in_attrs': False,
      'escape_rcdata': False,
      'force_html4_id': False,
      'indent_char': u' ',
      'inject_meta_charset': False,
      'max_depth': 6,
      'min_depth': 2,
      'minimize_boolean_attributes': False,
      'newline_char': u'\n',
      'omit_optional_tags': False,
      'output_encoding': 'utf-8',
      'parser': 'html5lib',
      'processes': set(['toc', 'xref', 'sub']),
      'profile': False,
      'quote_attr_values': True,
      'serializer': 'html5lib',
      'space_before_trailing_solidus': False,
      'strip_whitespace': None,
      'use_best_quote_char': False,
      'use_trailing_solidus': False,
      'w3c_compat_class_toc': False,
      'w3c_compat_crazy_substitutions': False,
      'w3c_compat_substitutions': False,
      'w3c_compat': True,
      'w3c_compat_xref_a_placement': False,
      'w3c_compat_xref_elements': False,
      'w3c_compat_xref_normalization': False,
    }
    if "anolis" in conf:
        opts.update(conf["anolis"])

    if spec == "srcset":
        print 'munging (before anolis)'

        filtered.seek(0)
        pre_anolis_buffer = StringIO()

        # Parse
        parser = html5lib.html5parser.HTMLParser(tree = html5lib.treebuilders.getTreeBuilder('lxml'))
        tree = parser.parse(filtered, encoding='utf-8')

        # Move introduction above conformance requirements
        introduction = tree.findall("//*[@id='introduction']")[0]
        intro_ps = introduction.xpath("following-sibling::*")
        target = tree.findall("//*[@id='conformance-requirements']")[0]
        target.addprevious(introduction)
        target = introduction
        target.addnext(intro_ps[2])
        target.addnext(intro_ps[1])
        target.addnext(intro_ps[0])

        # Serialize
        tokens = html5lib.treewalkers.getTreeWalker('lxml')(tree)
        serializer = html5lib.serializer.HTMLSerializer(quote_attr_values=True, inject_meta_charset=False)
        for text in serializer.serialize(tokens, encoding='utf-8'):
            pre_anolis_buffer.write(text)

        filtered = pre_anolis_buffer

    # replace data-x with data-anolis-xref
    print "fixing xrefs"
    filtered.seek(0)

    # Parse
    builder = treebuilders.getTreeBuilder("lxml", etree)
    try:
        parser = html5lib.HTMLParser(tree=builder, namespaceHTMLElements=False)
    except TypeError:
        parser = html5lib.HTMLParser(tree=builder)
    tree = parser.parse(filtered, encoding='utf-8')

    # Move introduction above conformance requirements
    data_x = tree.findall("//*[@data-x]")
    non_alphanumeric_spaces = re.compile(r"[^a-zA-Z0-9 \-\_\/\|]+")
    for refel in data_x:
        refel.attrib["data-anolis-xref"] = refel.get("data-x")
        if refel.tag == "dfn" and not refel.get("id", False) and refel.attrib["data-anolis-xref"]:
            refel.attrib["id"] = generateID(refel.attrib["data-anolis-xref"], refel)
        del refel.attrib["data-x"]
    # utils.ids = {}

    print 'indexing'
    # filtered.seek(0)
    # tree = generator.fromFile(filtered, **opts)
    generator.process(tree, **opts)
    filtered.close()

    # fixup nested dd's and dt's produced by lxml
    for dd in tree.findall('//dd/dd'):
        if list(dd) or dd.text.strip():
            dd.getparent().addnext(dd)
        else:
            dd.getparent().remove(dd)
    for dt in tree.findall('//dt/dt'):
        if list(dt) or dt.text.strip():
            dt.getparent().addnext(dt)
        else:
            dt.getparent().remove(dt)

    # remove unused references
    print "processing references"
    for dt in tree.findall("//dt[@id]"):
        refID = dt.get("id")
        if refID.startswith("refs") and len(tree.findall("//a[@href='#{0!s}']".format(refID))) == 0:
            next = dt.getnext()
            while next.tag != "dd":
                next = next.getnext()
            dt.getparent().remove(next)
            dt.getparent().remove(dt)
        elif refID.startswith("refs"):
            dd = dt.getnext()
            while dd.tag != "dd":
                dd = dd.getnext()
            links = dd.findall(".//a[@href]")
            for link in links:
                if link is not None:
                    wrap = link.getparent()
                    link.tail = " (URL: "
                    idx = wrap.index(link)
                    url = etree.Element("a", href=link.get("href"))
                    url.text = link.get("href")
                    wrap.insert(idx + 1, url)
                    url.tail = ")"

    if spec == "microdata":
        print 'munging (after anolis)'
        # get the h3 for the misplaced section (it has no container)
        section = tree.xpath("//h3[@id = 'htmlpropertiescollection']")[0]
        # then get all of its following siblings that have the h2 for the next section as 
        # a following sibling themselves. Yeah, XPath doesn't suck.
        section_content = section.xpath("following-sibling::*[following-sibling::h2[@id='introduction']]")
        target = tree.xpath("//h2[@id = 'converting-html-to-other-formats']")[0].getparent()
        target.addprevious(section)
        for el in section_content: target.addprevious(el)
        section.xpath("span")[0].text = "6.1 "
        # move the toc as well
        link = tree.xpath("//ol[@class='toc']//a[@href='#htmlpropertiescollection']")[0]
        link.xpath("span")[0].text = "6.1 "
        tree.xpath("//ol[@class='toc']/li[a[@href='#microdata-dom-api']]")[0].append(link.getparent().getparent())

    if spec == "srcset":
        print 'munging (after anolis)'
        # In the WHATWG spec, srcset="" is simply an aspect of
        # HTMLImageElement and not a separate feature. In order to keep
        # the HTML WG's srcset="" spec organized, we have to move some
        # things around in the final document.

        # Move "The srcset IDL attribute must reflect..."
        reflect_the_content_attribute = tree.findall("//div[@class='impl']")[0]
        target = tree.find("//div[@class='note']")
        target.addprevious(reflect_the_content_attribute)

        # Move "The IDL attribute complete must return true..."
        note_about_complete = tree.findall("//p[@class='note']")[4]
        p_otherwise = note_about_complete.xpath("preceding-sibling::p[position()=1]")[0]
        ul_conditions = p_otherwise.xpath("preceding-sibling::ul[position()=1]")[0]
        p_start = ul_conditions.xpath("preceding-sibling::p[position()=1]")[0]
        target.addnext(note_about_complete)
        target.addnext(p_otherwise)
        target.addnext(ul_conditions)
        target.addnext(p_start)

    try:
        os.makedirs(spec_dir)
    except:
        pass

    if spec == 'html':
        print 'cleaning'
        from glob import glob
        for name in glob("{0!s}/*.html".format(spec_dir)):
            os.remove(name)

        output = StringIO()
    else:
        output = open("{0!s}/Overview.html".format(spec_dir), 'wb')

    generator.toFile(tree, output, **opts)

    if spec != 'html':
        output.close()
    else:
        value = output.getvalue()
        if "<!--INTERFACES-->\n" in value:
            print 'interfaces'
            from interface_index import interface_index
            output.seek(0)
            index = StringIO()
            interface_index(output, index)
            value = value.replace("<!--INTERFACES-->\n", index.getvalue(), 1)
            index.close()
        output = open("{0!s}/single-page.html".format(spec_dir), 'wb')
        output.write(value)
        output.close()
        value = ''

        print 'splitting'
        import spec_splitter
        spec_splitter.w3c = True
        spec_splitter.no_split_exceptions = conf.get("no_split_exceptions", False)
        spec_splitter.minimal_split_exceptions = conf.get("minimal_split_exceptions", False)
        spec_splitter.main("{0!s}/single-page.html".format(spec_dir), spec_dir)

        print 'entities'
        entities = open(os.path.join(cur_dir, "boilerplate/entities.inc"))
        json = open("{0!s}/entities.json".format(spec_dir), 'w')
        from entity_processor_json import entity_processor_json
        entity_processor_json(entities, json)
        entities.close()
        json.close()

    # copying dependencies
    def copy_dependencies (targets):
        import types
        if not isinstance(targets, types.ListType): targets = [targets]
        if os.name == "nt":
            for target in targets:
                os.system("xcopy /s {0!s} {1!s}".format(os.path.join(conf["path"], target), spec_dir))
        else:
            for target in targets:
                os.system("/bin/csh -i -c '/bin/cp -R {0!s} {1!s}'".format(os.path.join(conf["path"], target), spec_dir))

    print "copying"
    if spec == "html":
        if os.name == "nt":
            dirs = ["images", "fonts", "404", "switcher", "js"]
        else:
            dirs = ["images", "fonts", "404/*", "switcher", "js"]
        copy_dependencies(dirs)
    elif spec == "2dcontext":
        copy_dependencies(["images", "fonts"])
    else:
        copy_dependencies("fonts")

    # fix the styling of the 404
    if spec == "html":
        link = tree.xpath("//link[starts-with(@href, 'http://www.w3.org/StyleSheets/TR/')]")[0].get("href")
        path = os.path.join(spec_dir, "404.html")
        with open(path) as data: html404 = data.read()
        html404 = html404.replace("http://www.w3.org/StyleSheets/TR/W3C-ED", link)
        with open(path, "w") as data: data.write(html404)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        invoked_incorrectly()
    spec = sys.argv[1]
    try:
        spec_dir = sys.argv[2]
    except IndexError:
        spec_dir = None
    try:
        branch = sys.argv[3]
    except IndexError:
        branch = None
    main(spec, spec_dir, branch)
