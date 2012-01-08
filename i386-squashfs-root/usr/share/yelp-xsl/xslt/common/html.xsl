<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<!--
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
details.

You should have received a copy of the GNU Lesser General Public License
along with this program; see the file COPYING.LGPL. If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
02111-1307, USA.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:html="http://www.w3.org/1999/xhtml"
                xmlns:exsl="http://exslt.org/common"
                xmlns:set="http://exslt.org/sets"
                xmlns:its="http://www.w3.org/2005/11/its"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="html set its"
                extension-element-prefixes="exsl"
                version="1.0">

<!--!!==========================================================================
HTML Output
Common utilities and CSS for transformations to HTML.
:Requires: gettext color icons
:Revision:version="1.0" date="2010-05-26" status="final"

This stylesheet contains common templates for creating HTML output. The
*{html.output} template creates an output file for a node in the source XML
document, calling *{html.page} to create the actual output. Output files can
be either XHTML or HTML, depending on the @{html.xhtml} parameter.

This stylesheet matches #{/} and calls *{html.output} on the root XML element.
This works for most input formats. If you need to do something different, you
should override the match for #{/}.
-->
<xsl:template match="/">
  <xsl:call-template name="html.output">
    <xsl:with-param name="node" select="*"/>
  </xsl:call-template>
</xsl:template>



<!--@@==========================================================================
html.basename
The base filename of the primary output file.
:Revision:version="1.0" date="2010-05-25" status="final"

This parameter specifies the base filename of the primary output file, without
the filename extension. This is used by *{html.output} to determine the output
filename, and may be used by format-specific linking code. By default, it uses
the value of an #{id} or #{xml:id} attribute, if present. Otherwise, it uses
the static string #{index}.
-->
<xsl:param name="html.basename">
  <xsl:choose>
    <xsl:when test="/*/@xml:id">
      <xsl:value-of select="/*/@xml:id"/>
    </xsl:when>
    <xsl:when test="/*/@id">
      <xsl:value-of select="/*/@id"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:text>index</xsl:text>
    </xsl:otherwise>
  </xsl:choose>
</xsl:param>


<!--@@==========================================================================
html.xhtml
Whether to output XHTML.
:Revision:version="1.0" date="2010-05-25" status="final"

If this parameter is set to true, this stylesheet will output XHTML. Otherwise,
the output is assumed to be HTML. Note that for HTML output, the importing
stylesheet still needs to call #{xsl:namespace-alias} to map the XHTML namespace
to #{#default}. The @{html.namespace} will be set automatically based on this
parameter. Stylesheets can use this parameter to check the output type, for
example when using #{xsl:element}.
-->
<xsl:param name="html.xhtml" select="true()"/>


<!--@@==========================================================================
html.namespace
The XML namespace for the output document.
:Revision:version="1.0" date="2010-05-25" status="final"

This parameter specifies the XML namespace of all output documents. It will be
set automatically based on the ${html.xhtml} parameter, either to the XHTML
namespace, or to the empty namespace. Stylesheets can use this parameter when
using #{xsl:element}.
-->
<xsl:param name="html.namespace">
  <xsl:choose>
    <xsl:when test="$html.xhtml">
      <xsl:value-of select="'http://www.w3.org/1999/xhtml'"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:text></xsl:text>
    </xsl:otherwise>
  </xsl:choose>
</xsl:param>


<!--@@==========================================================================
html.extension
The filename extension for all output files.
:Revision:version="1.0" date="2010-05-25" status="final"

This parameter specifies a filename extension for all HTML output files. It
should include the leading dot. By default, #{.xhtml} will be used if
@{html.xhtml} is true; otherwise, #{.html} will be used.
-->
<xsl:param name="html.extension">
  <xsl:choose>
    <xsl:when test="$html.xhtml">
      <xsl:text>.xhtml</xsl:text>
    </xsl:when>
    <xsl:otherwise>
      <xsl:text>.html</xsl:text>
    </xsl:otherwise>
  </xsl:choose>
</xsl:param>


<!--@@==========================================================================
html.css.root
The URI root for external CSS files.
:Revision:version="1.0" date="2010-12-06" status="final"

This parameter provides a root URI for any external CSS files that are
referenced from the output HTML file. If non-empty, it must end with
a trailing slash character.
-->
<xsl:param name="html.css.root" select="''"/>


<!--@@==========================================================================
html.js.root
The URI root for external JavaScript files.
:Revision:version="1.0" date="2010-12-06" status="final"

This parameter provides a root URI for any external JavaScript files that are
referenced from the output HTML file. If non-empty, it must end with
a trailing slash character.
-->
<xsl:param name="html.js.root" select="''"/>


<!--@@==========================================================================
html.syntax.highlight
Whether to include syntax highlighting support for code blocks.
:Revision:version="1.0" date="2010-12-06" status="final"

This parameter specifies whether syntax highlighting should be enabled for
code blocks in the output HTML. Syntax highlighting is done at document load
time by JavaScript.
-->
<xsl:param name="html.syntax.highlight" select="true()"/>


<!--**==========================================================================
html.output
Create an HTML output file.
:Revision:version="1.0" date="2010-05-26" status="final"
$node: The node to create an output file for.
$href: The output filename.

This template creates an HTML output file for the source element ${node}. It
uses #{exsl:document} to output the file, and calls *{html.page} with the
${node} parameter to output the actual HTML contents.

If ${href} is not provided, this template will attempt to generate a base
filename and append @{html.extension} to it. The base filename is generated
as follows: If an #{xml:id} attribute is present, it is used; otherwise, if
an #{id} attribute is present, it is uses; otherwise, if ${node} is the root
element, @{html.basename} is used; otherwise, #{generate-id()} is called.

After calling #{exsl:document}, this template calls the %{html.output.after.mode}
mode on ${node}. Importing stylesheets that create multiple output files can
use this to process output files without blocking earlier output.
-->
<xsl:template name="html.output">
  <xsl:param name="node" select="."/>
  <xsl:param name="href">
    <xsl:choose>
      <xsl:when test="$node/@xml:id">
        <xsl:value-of select="concat($node/@xml:id, $html.extension)"/>
      </xsl:when>
      <xsl:when test="$node/@id">
        <xsl:value-of select="concat($node/@id, $html.extension)"/>
      </xsl:when>
      <xsl:when test="set:has-same-node($node, /*)">
        <xsl:value-of select="concat($html.basename, $html.extension)"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="concat(generate-id(), $html.extension)"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:param>
  <exsl:document href="{$href}">
    <xsl:call-template name="html.page">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </exsl:document>
  <xsl:apply-templates mode="html.output.after.mode" select="$node"/>
</xsl:template>



<!--%%==========================================================================
html.output.after.mode
Process an element after its content are output.
:Revision:version="1.0" date="2010-05-26" status="final"

This mode is called by *{html.output} after #{exsl:document} has finished. It
can be used to create further output files without blocking the output of
parent elements.
-->
<xsl:template mode="html.output.after.mode" match="*"/>


<!--**==========================================================================
html.page
Create an HTML document.
:Revision:version="1.0" date="2010-05-26" status="final"
$node: The node to create HTML for.

This template creates the actual HTML output for ${node}. It outputs top-level
elements and container divs, and calls various templates and modes to output
the inner content. Importing stylesheets should implement at least
%{html.title.mode} and %{html.body.mode} for any elements that could be passed
as ${node} to this template.
-->
<xsl:template name="html.page">
  <xsl:param name="node" select="."/>
  <html>
    <head>
      <title>
        <xsl:apply-templates mode="html.title.mode" select="$node"/>
      </title>
      <xsl:call-template name="html.css"/>
      <xsl:call-template name="html.js"/>
      <xsl:call-template name="html.head.custom"/>
    </head>
    <body>
      <xsl:apply-templates mode="html.body.attr.mode" select="$node"/>
      <div class="header">
        <xsl:apply-templates mode="html.header.mode" select="$node"/>
      </div>
      <div class="body">
        <xsl:apply-templates mode="html.body.mode" select="$node"/>
      </div>
      <div class="footer">
        <xsl:apply-templates mode="html.footer.mode" select="$node"/>
      </div>
    </body>
  </html>
</xsl:template>


<!--%%==========================================================================
html.title.mode
Output the title of an element.
:Revision:version="1.0" date="2010-05-26" status="final"

This mode is called by *{html.page} to output the contents of the HTML #{title}
element inside the #{head} element. Importing stylesheets should implement this
mode for any element that will be passed to *{html.page}. Because this is used
in the #{head}, the output should be text-only.
-->
<xsl:template mode="html.title.mode" match="*"/>


<!--%%==========================================================================
html.body.attr.mode
Output attributes for the HTML #{body} element.
:Revision:version="1.0" date="2010-06-08" status="final"

This mode is called by *{html.page} to output attributes on the HTML #{body}
element. No attributes are output by default. Importing stylesheets may
implement this node to add attributes for styling, data, or other purposes.
-->
<xsl:template mode="html.body.attr.mode" match="*"/>


<!--%%==========================================================================
html.header.mode
Output the header content for an element.
:Revision:version="1.0" date="2010-05-26" status="final"

This mode is called by *{html.page} to output the contents of the header div
above the main content. Importing stylesheets may implement this mode for any
element that will be passed to *{html.page}. If they do not, the header div
will be empty.
-->
<xsl:template mode="html.header.mode" match="*"/>


<!--%%==========================================================================
html.footer.mode
Output the footer content for an element.
:Revision:version="1.0" date="2010-05-26" status="final"

This mode is called by *{html.page} to output the contents of the footer div
below the main content. Importing stylesheets may implement this mode for any
element that will be passed to *{html.page}. If they do not, the footer div
will be empty.
-->
<xsl:template mode="html.footer.mode" match="*"/>


<!--%%==========================================================================
html.body.mode
Output the main contents for an element.
:Revision:version="1.0" date="2010-05-26" status="final"

This mode is called by *{html.page} to output the main contents of an HTML
page, below the header content and above the footer content. Titles, block
content, and sections should be output in this mode.
-->
<xsl:template mode="html.body.mode" match="*"/>


<!--**==========================================================================
html.head.custom
Stub to output custom content for the HTML #{head} element.
:Stub: true
:Revision: version="1.0" date="2010-05-25" status="final"

This template is a stub, called by *{html.page}. You can override this template
to provide additional elements in the HTML #{head} element of output files.
-->
<xsl:template name="html.head.custom">
  <xsl:param name="node" select="."/>
</xsl:template>


<!--**==========================================================================
html.css
Output all CSS for an HTML output page.
:Revision:version="1.0" date="2010-12-23" status="final"
$node: The node to create CSS for.
$direction: The directionality of the text, either #{ltr} or #{rtl}.
$left: The starting alignment, either #{left} or #{right}.
$right: The ending alignment, either #{left} or #{right}.

This template creates the CSS for an HTML output page, including the enclosing
HTML #{style} element. It calls the templates *{html.css.content} to output the
actual CSS contents.

The ${direction} parameter specifies the directionality of the text for the
language of the document. The ${left} and ${right} parameters are based on
${direction}, and can be used to set beginning and ending margins or other
dimensions. All parameters can be automatically computed if not provided.
-->
<xsl:template name="html.css">
  <xsl:param name="node" select="."/>
  <xsl:param name="direction">
    <xsl:call-template name="l10n.direction"/>
  </xsl:param>
  <xsl:param name="left">
    <xsl:call-template name="l10n.align.start">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="right">
    <xsl:call-template name="l10n.align.end">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <style type="text/css">
    <xsl:call-template name="html.css.content">
      <xsl:with-param name="node" select="$node"/>
      <xsl:with-param name="direction" select="$direction"/>
      <xsl:with-param name="left" select="$left"/>
      <xsl:with-param name="right" select="$right"/>
    </xsl:call-template>
  </style>
</xsl:template>


<!--**==========================================================================
html.css.content
Output actual CSS content for an HTML output page.
:Revision:version="1.0" date="2010-12-23" status="final"
$node: The node to create CSS for.
$direction: The directionality of the text, either #{ltr} or #{rtl}.
$left: The starting alignment, either #{left} or #{right}.
$right: The ending alignment, either #{left} or #{right}.

This template creates the CSS content for an HTML output page. It is called by
*{html.css}. It calls the templates *{html.css.core}, *{html.css.elements}, and
*{html.css.syntax}. It then calls the mode %{html.css.mode} on ${node} and
calls the template *{html.css.custom}.
-->
<xsl:template name="html.css.content">
  <xsl:param name="node" select="."/>
  <xsl:param name="direction">
    <xsl:call-template name="l10n.direction"/>
  </xsl:param>
  <xsl:param name="left">
    <xsl:call-template name="l10n.align.start">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="right">
    <xsl:call-template name="l10n.align.end">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:call-template name="html.css.core">
    <xsl:with-param name="node" select="$node"/>
    <xsl:with-param name="direction" select="$direction"/>
    <xsl:with-param name="left" select="$left"/>
    <xsl:with-param name="right" select="$right"/>
  </xsl:call-template>
  <xsl:call-template name="html.css.elements">
    <xsl:with-param name="node" select="$node"/>
    <xsl:with-param name="direction" select="$direction"/>
    <xsl:with-param name="left" select="$left"/>
    <xsl:with-param name="right" select="$right"/>
  </xsl:call-template>
  <xsl:call-template name="html.css.syntax">
    <xsl:with-param name="node" select="$node"/>
    <xsl:with-param name="direction" select="$direction"/>
    <xsl:with-param name="left" select="$left"/>
    <xsl:with-param name="right" select="$right"/>
  </xsl:call-template>
  <xsl:apply-templates mode="html.css.mode" select="$node">
    <xsl:with-param name="direction" select="$direction"/>
    <xsl:with-param name="left" select="$left"/>
    <xsl:with-param name="right" select="$right"/>
  </xsl:apply-templates>
  <xsl:call-template name="html.css.custom">
    <xsl:with-param name="node" select="$node"/>
    <xsl:with-param name="direction" select="$direction"/>
    <xsl:with-param name="left" select="$left"/>
    <xsl:with-param name="right" select="$right"/>
  </xsl:call-template>
</xsl:template>


<!--%%==========================================================================
html.css.mode
Output CSS specific to the input format.
:Revision:version="1.0" date="2010-05-26" status="final"
$direction: The directionality of the text, either #{ltr} or #{rtl}.
$left: The starting alignment, either #{left} or #{right}.
$right: The ending alignment, either #{left} or #{right}.

This template is called by *{html.css.content} to output CSS specific to the
input format. Importing stylesheets may implement this for any element that
will be passed to *{html.page}. If they do not, the output HTML will only have
the common CSS.
-->
<xsl:template mode="html.css.mode" match="*">
  <xsl:param name="direction">
    <xsl:call-template name="l10n.direction"/>
  </xsl:param>
  <xsl:param name="left">
    <xsl:call-template name="l10n.align.start">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="right">
    <xsl:call-template name="l10n.align.end">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
</xsl:template>


<!--**==========================================================================
html.css.core
Output CSS that does not reference source elements.
:Revision: version="1.0" date="2010-05-25" status="final"
$node: The node to create CSS for.
$direction: The directionality of the text, either #{ltr} or #{rtl}.
$left: The starting alignment, either #{left} or #{right}.
$right: The ending alignment, either #{left} or #{right}.

This template outputs CSS that can be used in any HTML. It does not reference
elements from DocBook, Mallard, or other source languages. It provides the
common spacings for block-level elements lik paragraphs and lists, defines
styles for links, and defines four common wrapper divs: #{header}, #{side},
#{body}, and #{footer}.

All parameters can be automatically computed if not provided.
-->
<xsl:template name="html.css.core">
  <xsl:param name="node" select="."/>
  <xsl:param name="direction">
    <xsl:call-template name="l10n.direction"/>
  </xsl:param>
  <xsl:param name="left">
    <xsl:call-template name="l10n.align.start">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="right">
    <xsl:call-template name="l10n.align.end">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:text>
html { height: 100%; }
body {
  margin: 0; padding: 0;
  background-color: </xsl:text>
    <xsl:value-of select="$color.gray_background"/><xsl:text>;
  color: </xsl:text>
    <xsl:value-of select="$color.text"/><xsl:text>;
  direction: </xsl:text><xsl:value-of select="$direction"/><xsl:text>;
}
div.body {
  margin: 0;
  padding: 1em;
  max-width: 60em;
  min-height: 20em;
  background-color: </xsl:text>
    <xsl:value-of select="$color.background"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
div.header {
  max-width: 60em;
}
div.footer {
  max-width: 60em;
}
div.sect {
  margin-top: 1.72em;
  clear: both;
}
div.sect div.sect {
  margin-top: 1.44em;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1.72em;
}
div.trails { margin: 0; }
div.trail {
  font-size: 0.83em;
  margin: 0 2.2em 0.2em 2.2em;
  padding: 0;
  text-indent: -1em;
  color: </xsl:text>
    <xsl:value-of select="$color.text_light"/><xsl:text>;
}
a.trail { white-space: nowrap; }
div.hgroup {
  margin: 0 0 0.5em 0;
  color: </xsl:text>
    <xsl:value-of select="$color.text_light"/><xsl:text>;
  border-bottom: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
h1, h2, h3, h4, h5, h6, h7 {
  margin: 0; padding: 0;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
  font-weight: bold;
}
h1 { font-size: 1.44em; }
h2 { font-size: 1.2em; }
h3.title, h4.title, h5.title, h6.title, h7.title { font-size: 1.2em; }
h3, h4, h5, h6, h7 { font-size: 1em; }

p { line-height: 1.72em; }
div, pre, p { margin: 1em 0 0 0; padding: 0; }
div:first-child, pre:first-child, p:first-child { margin-top: 0; }
div.inner, div.region, div.contents, pre.contents { margin-top: 0; }
pre.contents div { margin-top: 0 !important; }
p img { vertical-align: middle; }
div.clear {
  margin: 0; padding: 0;
  height: 0; line-height: 0;
  clear: both;
}

table {
  border-collapse: collapse;
  border-color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
  border-width: 1px;
}
td, th {
  padding: 0.5em;
  vertical-align: top;
  border-color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
  border-width: 1px;
}
thead td, thead th, tfoot td, tfoot th {
  padding: 0.2em 0.5em 0.2em 0.5em;
}

ul, ol, dl { margin: 0; padding: 0; }
li {
  margin: 1em 0 0 0;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 2.4em;
  padding: 0;
}
li:first-child { margin-top: 0; }
dt { margin-top: 1em; }
dt:first-child { margin-top: 0; }
dt + dt { margin-top: 0; }
dd {
  margin: 0.2em 0 0 0;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1.44em;
}
ol.compact li { margin-top: 0.2em; }
ul.compact li { margin-top: 0.2em; }
ol.compact li:first-child { margin-top: 0; }
ul.compact li:first-child { margin-top: 0; }
dl.compact dt { margin-top: 0.2em; }
dl.compact dt:first-child { margin-top: 0; }
dl.compact dt + dt { margin-top: 0; }

a {
  text-decoration: none;
  color: </xsl:text><xsl:value-of select="$color.link"/><xsl:text>;
}
a:visited { color: </xsl:text>
  <xsl:value-of select="$color.link_visited"/><xsl:text>; }
a:hover { text-decoration: underline; }
a img { border: none; }
</xsl:text>
</xsl:template>


<!--**==========================================================================
html.css.elements
Output CSS for common elements from source formats.
:Revision: version="1.0" date="2010-05-25" status="final"
$node: The node to create CSS for.
$direction: The directionality of the text, either #{ltr} or #{rtl}.
$left: The starting alignment, either #{left} or #{right}.
$right: The ending alignment, either #{left} or #{right}.

This template outputs CSS for elements from source languages like DocBook and
Mallard. It defines them using common class names. The common names are often
the simpler element names from Mallard, although there some class names which
are not taken from Mallard. Stylesheets which convert to HTML should use the
appropriate common classes.

All parameters can be automatically computed if not provided.
-->
<xsl:template name="html.css.elements">
  <xsl:param name="node" select="."/>
  <xsl:param name="direction">
    <xsl:call-template name="l10n.direction"/>
  </xsl:param>
  <xsl:param name="left">
    <xsl:call-template name="l10n.align.start">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="right">
    <xsl:call-template name="l10n.align.end">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:text>
div.title {
  margin: 0 0 0.2em 0;
  font-weight: bold;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
div.title h1, div.title h2, div.title h3, div.title h4, div.title h5, div.title h6 {
  margin: 0;
  font-size: inherit;
  font-weight: inherit;
  color: inherit;
}
div.desc { margin: 0 0 0.2em 0; }
div.contents + div.desc { margin: 0.2em 0 0 0; }
pre.contents {
  padding: 0.5em 1em 0.5em 1em;
}
div.links > div.inner > div.title span.title {
  border-bottom: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
div.links .desc { color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>; }
div.links ul { margin: 0; padding: 0; }
li.links {
  margin: 0.5em 0 0.5em 0;
  padding: 0;
  padding-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1em;
  list-style-type: none;
}
div.sectionlinks {
  display: inline-block;
  padding: 0 1em 0 1em;
  background-color: </xsl:text>
    <xsl:value-of select="$color.blue_background"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
}
div.sectionlinks ul { margin: 0; }
div.sectionlinks li { padding: 0; }
div.sectionlinks div.title { margin: 0.5em 0 0.5em 0; }
div.sectionlinks div.title span.title {
  border-bottom: solid 1px </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
}
div.sectionlinks div.sectionlinks {
  display: block;
  margin: 0.5em 0 0 0;
  padding: 0;
  border: none;
}
div.sectionlinks div.sectionlinks li {
  padding-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1.44em;
}
div.nextlinks {
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1.2em;
  float: </xsl:text><xsl:value-of select="$right"/><xsl:text>;
  clear: both;
}
a.nextlinks-prev::before {
  content: '</xsl:text><xsl:choose>
  <xsl:when test="$left = 'left'"><xsl:text>&#x25C0;&#x00A0;&#x00A0;</xsl:text></xsl:when>
  <xsl:otherwise><xsl:text>&#x25B6;&#x00A0;&#x00A0;</xsl:text></xsl:otherwise>
  </xsl:choose><xsl:text>';
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
  vertical-align: bottom;
}
a.nextlinks-next::after {
  content: '</xsl:text><xsl:choose>
  <xsl:when test="$left = 'left'"><xsl:text>&#x00A0;&#x00A0;&#x25B6;</xsl:text></xsl:when>
  <xsl:otherwise><xsl:text>&#x00A0;&#x00A0;&#x25C0;</xsl:text></xsl:otherwise>
  </xsl:choose><xsl:text>';
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
div.serieslinks {
  display: inline-block;
  padding: 0 1em 0 1em;
  background-color: </xsl:text>
    <xsl:value-of select="$color.blue_background"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
}
div.serieslinks ul { margin: 0; }
div.serieslinks li { padding: 0; }
div.serieslinks div.title { margin: 0.5em 0 0.5em 0; }
div.serieslinks div.title span.title {
  border-bottom: solid 1px </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
}
pre.numbered {
  margin: 0;
  padding: 0.5em;
  float: </xsl:text><xsl:value-of select="$left"/><xsl:text>;
  margin-</xsl:text><xsl:value-of select="$right"/><xsl:text>: 0.5em;
  text-align: </xsl:text><xsl:value-of select="$right"/><xsl:text>;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.yellow_background"/><xsl:text>;
}
div.code {
  background: url('</xsl:text>
    <xsl:value-of select="$icons.code"/><xsl:text>') no-repeat top </xsl:text>
    <xsl:value-of select="$right"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
div.figure {
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1.72em;
  padding: 4px;
  color: </xsl:text>
    <xsl:value-of select="$color.text_light"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.gray_background"/><xsl:text>;
}
div.figure > div.inner > a.zoom {
  float: </xsl:text><xsl:value-of select="$right"/><xsl:text>;
}
div.figure > div.inner > div.region > div.contents {
  margin: 0;
  padding: 0.5em 1em 0.5em 1em;
  clear: both;
  text-align: center;
  color: </xsl:text>
    <xsl:value-of select="$color.text"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.background"/><xsl:text>;
}
div.list > div.inner > div.title { margin-bottom: 0.5em; }
div.listing > div.inner { margin: 0; padding: 0; }
div.listing > div.inner > div.region > div.desc { font-style: italic; }
div.note {
  padding: 6px;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.dark_background"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.gray_background"/><xsl:text>;
}
div.note > div.inner > div.title {
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: </xsl:text>
    <xsl:value-of select="$icons.size.note + 6"/><xsl:text>px;
}
div.note > div.inner > div.region > div.contents {
  margin: 0; padding: 0;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: </xsl:text>
    <xsl:value-of select="$icons.size.note + 6"/><xsl:text>px;
}
div.note > div.inner {
  margin: 0; padding: 0;
  background-image: url("</xsl:text>
    <xsl:value-of select="$icons.note"/><xsl:text>");
  background-position: </xsl:text><xsl:value-of select="$left"/><xsl:text> top;
  background-repeat: no-repeat;
  min-height: </xsl:text><xsl:value-of select="$icons.size.note"/><xsl:text>px;
}
div.note-advanced > div.inner { <!-- background-image: url("</xsl:text>
  <xsl:value-of select="$icons.note.advanced"/><xsl:text>"); --> }
div.note-bug > div.inner { background-image: url("</xsl:text>
  <xsl:value-of select="$icons.note.bug"/><xsl:text>"); }
div.note-important > div.inner { background-image: url("</xsl:text>
  <xsl:value-of select="$icons.note.important"/><xsl:text>"); }
div.note-tip > div.inner { background-image: url("</xsl:text>
  <xsl:value-of select="$icons.note.tip"/><xsl:text>"); }
div.note-warning > div.inner { background-image: url("</xsl:text>
  <xsl:value-of select="$icons.note.warning"/><xsl:text>"); }
div.note-sidebar {
  float: </xsl:text><xsl:value-of select="$right"/><xsl:text>;
  max-width: 40%;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 6px;
  padding: 6px;
}
div.note-sidebar > div.inner { background-image: none; }
div.note-sidebar > div.inner > div.title { margin-</xsl:text>
  <xsl:value-of select="$left"/><xsl:text>: 0px; }
div.note-sidebar > div.inner > div.region > div.contents { margin-</xsl:text>
  <xsl:value-of select="$left"/><xsl:text>: 0px; }
div.quote {
  padding: 0;
  background-image: url('</xsl:text>
    <xsl:value-of select="$icons.quote"/><xsl:text>');
  background-repeat: no-repeat;
  background-position: top </xsl:text><xsl:value-of select="$left"/><xsl:text>;
  min-height: </xsl:text>
    <xsl:value-of select="$icons.size.quote"/><xsl:text>px;
}
div.quote > div.inner > div.title {
  margin: 0 0 0.5em 0;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: </xsl:text>
    <xsl:value-of select="$icons.size.quote"/><xsl:text>px;
}
blockquote {
  margin: 0; padding: 0;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: </xsl:text>
    <xsl:value-of select="$icons.size.quote"/><xsl:text>px;
}
div.quote > div.inner > div.region > div.cite {
  margin-top: 0.5em;
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: </xsl:text>
    <xsl:value-of select="$icons.size.quote"/><xsl:text>px;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
div.quote > div.inner > div.region > div.cite::before {
  <!-- FIXME: i18n -->
  content: '&#x2015; ';
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
div.screen {
  background-color: </xsl:text>
    <xsl:value-of select="$color.gray_background"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
ol.steps, ul.steps {
  margin: 0;
  padding: 0.5em 1em 0.5em 1em;
  border-</xsl:text><xsl:value-of select="$left"/><xsl:text>: solid 4px </xsl:text>
    <xsl:value-of select="$color.yellow_border"/><xsl:text>;
  -moz-box-shadow: 0 1px 2px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  -webkit-box-shadow: 0 1px 2px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  box-shadow: 0 1px 2px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
ol.steps .steps {
  padding: 0;
  border: none;
  background-color: none;
  -moz-box-shadow: none;
  -webkit-box-shadow: none;
  box-shadow: none;
}
li.steps { margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1.44em; }
li.steps li.steps { margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 2.4em; }
div.synopsis > div.inner > div.region > div.contents, div.synopsis > pre.contents {
  padding: 0.5em 1em 0.5em 1em;
  border-top: solid 1px;
  border-bottom: solid 1px;
  border-color: </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.gray_background"/><xsl:text>;
}
div.synopsis > div.inner > div.region > div.desc { font-style: italic; }
div.synopsis div.code {
  background: none;
  border: none;
  padding: 0;
}
div.synopsis div.code > pre.contents { margin: 0; padding: 0; }
div.table > div.desc { font-style: italic; }
tr.shade {
  background-color: </xsl:text><xsl:value-of select="$color.gray_background"/><xsl:text>;
}
td.shade {
  background-color: </xsl:text><xsl:value-of select="$color.gray_background"/><xsl:text>;
}
tr.shade td.shade {
  background-color: </xsl:text><xsl:value-of select="$color.dark_background"/><xsl:text>;
}

span.app { font-style: italic; }
span.cmd {
  font-family: monospace;
  background-color: </xsl:text>
    <xsl:value-of select="$color.gray_background"/><xsl:text>;
  padding: 0 0.2em 0 0.2em;
}
span.cmd span.cmd { background-color: none; padding: 0; }
pre span.cmd { background-color: none; padding: 0; }
span.code {
  font-family: monospace;
  border-bottom: solid 1px </xsl:text><xsl:value-of select="$color.dark_background"/><xsl:text>;
}
span.code span.code { border: none; }
pre span.code { border: none; }
span.em { font-style: italic; }
span.em-bold {
  font-style: normal; font-weight: bold;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
pre span.error {
  color: </xsl:text><xsl:value-of select="$color.text_error"/><xsl:text>;
}
span.file { font-family: monospace; }
span.gui, span.guiseq { color: </xsl:text>
  <xsl:value-of select="$color.text_light"/><xsl:text>; }
span.input { font-family: monospace; }
pre span.input {
  font-weight: bold;
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
span.key {
  color: </xsl:text>
    <xsl:value-of select="$color.text_light"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.yellow_border"/><xsl:text>;
  padding: 0 0.2em 0 0.2em;
  white-space: nowrap
}
span.keyseq {
  color: </xsl:text>
    <xsl:value-of select="$color.text_light"/><xsl:text>;
  white-space: nowrap
}
span.output { font-family: monospace; }
pre span.output {
  color: </xsl:text><xsl:value-of select="$color.text"/><xsl:text>;
}
pre span.prompt {
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
span.sys { font-family: monospace; }
span.var { font-style: italic; }
div.media-video &gt; div.inner { display: inline-block; text-align: center; }
div.media-video &gt; div.inner video { margin: 0; }
div.media-controls {
  min-width: 24em;
  height: 24px;
  margin: 0; padding: 4px;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.text"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.text_light"/><xsl:text>;
  color: </xsl:text>
    <xsl:value-of select="$color.background"/><xsl:text>;
}
button.media-play {
  height: 24px;
  float: </xsl:text><xsl:value-of select="$left"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.gray_background"/><xsl:text>;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  padding: 0; line-height: 0;
  -moz-border-radius: 2px;
  -webkit-border-radius: 2px;
  border-radius: 2px;
}
button.media-play:hover, button.media-play:focus {
  background-color: </xsl:text>
    <xsl:value-of select="$color.blue_background"/><xsl:text>;
  border-color: </xsl:text>
    <xsl:value-of select="$color.blue_border"/><xsl:text>;
  -moz-box-shadow: 0 0 2px </xsl:text>
    <xsl:value-of select="$color.blue_background"/><xsl:text>;
  -webkit-box-shadow: 0 0 2px </xsl:text>
    <xsl:value-of select="$color.blue_background"/><xsl:text>;
  box-shadow: 0 0 2px </xsl:text>
    <xsl:value-of select="$color.blue_background"/><xsl:text>;
}
button.media-play canvas { margin: 0; }
div.media-range {
  display: inline-block;
  margin: 2px 8px 0 8px;
  padding: 0;
  height: 20px;
}
span.media-current {
  float: </xsl:text><xsl:value-of select="$right"/><xsl:text>;
  font-size: 16px;
  line-height: 20px;
}
div.media-ttml { margin: 0; padding: 0; }
div.media-ttml-p {
  text-align: </xsl:text><xsl:value-of select="$left"/><xsl:text>;
  display: none;
  margin: 6px auto 0 auto;
  padding: 6px;
  max-width: 24em;
  border: solid 1px </xsl:text>
    <xsl:value-of select="$color.yellow_border"/><xsl:text>;
  background-color: </xsl:text>
    <xsl:value-of select="$color.yellow_background"/><xsl:text>;
  -moz-box-shadow: 2px 2px 4px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  -webkit-box-shadow: 2px 2px 4px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
  box-shadow: 2px 2px 4px </xsl:text>
    <xsl:value-of select="$color.gray_border"/><xsl:text>;
}
div.yelp-data { display: none; }
div.ui-expander > div.inner > div.title:hover,
div.ui-expander > div.inner > div.hgroup:hover * {
  color: </xsl:text><xsl:value-of select="$color.link"/><xsl:text>;
}
div.ui-expander > div.inner > div.hgroup > .subtitle {
  margin-</xsl:text><xsl:value-of select="$left"/><xsl:text>: 1.44em;
}
div.ui-expander-e > div.inner > div.title span.ui-expander-arrow-ltr,
div.ui-expander-e > div.inner > div.hgroup span.ui-expander-arrow-ltr {
  display: inline-block; <!-- webkit needs this to rotate -->
  -moz-transform: rotate(90deg);
  -webkit-transform: rotate(90deg);
  -o-transform: rotate(90deg);
  -ms-transform: rotate(90deg);
  transform: rotate(90deg);
}
div.ui-expander-e > div.inner > div.title span.ui-expander-arrow-rtl,
div.ui-expander-e > div.inner > div.hgroup span.ui-expander-arrow-rtl {
  display: inline-block; <!-- webkit needs this to rotate -->
  -moz-transform: rotate(-90deg);
  -webkit-transform: rotate(-90deg);
  -o-transform: rotate(-90deg);
  -ms-transform: rotate(-90deg);
  transform: rotate(-90deg);
}
</xsl:text>
</xsl:template>


<!--**==========================================================================
html.css.syntax
Output CSS for syntax highlighting.
:Revision: version="1.0" date="2010-12-06" status="final"
$node: The node to create CSS for.
$direction: The directionality of the text, either #{ltr} or #{rtl}.
$left: The starting alignment, either #{left} or #{right}.
$right: The ending alignment, either #{left} or #{right}.

This template outputs CSS to support syntax highlighting of code blocks. Syntax
highlighting is done at document load time with JavaScript. Text in code blocks
is broken up into chunks and wrapped in HTML elements with particular classes.
This template outputs CSS to match those elements and style them with the
built-in themeable colors from !{colors}.

All parameters can be automatically computed if not provided.
-->
<xsl:template name="html.css.syntax">
  <xsl:param name="node" select="."/>
  <xsl:param name="direction">
    <xsl:call-template name="l10n.direction"/>
  </xsl:param>
  <xsl:param name="left">
    <xsl:call-template name="l10n.align.start">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="right">
    <xsl:call-template name="l10n.align.end">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:if test="$html.syntax.highlight">
  <xsl:text>
pre.syntax span.function, pre.syntax span.keyword, pre.syntax span.tag {
  color: </xsl:text><xsl:value-of select="$color.blue_border"/><xsl:text>;
}
pre.syntax span.string, pre.syntax span.operator {
  color: </xsl:text><xsl:value-of select="$color.text_light"/><xsl:text>;
}
</xsl:text>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
html.css.custom
Stub to output custom CSS common to all HTML transformations.
:Stub: true
:Revision: version="1.0" date="2010-05-25" status="final"
$node: The node to create CSS for.
$direction: The directionality of the text, either #{ltr} or #{rtl}.
$left: The starting alignment, either #{left} or #{right}.
$right: The ending alignment, either #{left} or #{right}.

This template is a stub, called by *{html.css.content}. You can override this
template to provide additional CSS that will be used by all HTML output.
-->
<xsl:template name="html.css.custom">
  <xsl:param name="node" select="."/>
  <xsl:param name="direction">
    <xsl:call-template name="l10n.direction"/>
  </xsl:param>
  <xsl:param name="left">
    <xsl:call-template name="l10n.align.start">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="right">
    <xsl:call-template name="l10n.align.end">
      <xsl:with-param name="direction" select="$direction"/>
    </xsl:call-template>
  </xsl:param>
</xsl:template>


<!--**==========================================================================
html.js
Output all JavaScript for an HTML output page.
:Revision:version="1.0" date="2010-12-31" status="final"
$node: The node to create JavaScript for.

This template creates the JavaScript for an HTML output page. It calls the
template *{html.js.jquery} to output references to jQuery files. It then
calls *{html.js.custom} to output references to custom JavaScript files.
Finally, it outputs an HTML #{script} tag and calls *{html.js.content} to
ouput the contents of that tag.
-->
<xsl:template name="html.js">
  <xsl:param name="node" select="."/>
  <xsl:call-template name="html.js.jquery">
    <xsl:with-param name="node" select="$node"/>
  </xsl:call-template>
  <xsl:call-template name="html.js.custom">
    <xsl:with-param name="node" select="$node"/>
  </xsl:call-template>
  <script type="text/javascript">
    <xsl:call-template name="html.js.content">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </script>
</xsl:template>


<!--**==========================================================================
html.js.jquery
Output references to jQuery JavaScript files.
:Revision: version="1.0" date="2010-12-31" status="final"
$node: The node to create JavaScript for.

This template outputs HTML #{script} tags to reference any necessary jQuery files.
It always includes a reference to #{jquery.js}. If @{html.syntax.highlight} is
#{true}, it will also include a reference to #{jquery.syntax.js} along with an
additional #{script} tag to initialize syntax highlighting. All references are
output relative to @{html.js.root}.
-->
<xsl:template name="html.js.jquery">
  <xsl:param name="node" select="."/>
  <script type="text/javascript">
    <xsl:attribute name="src">
      <xsl:value-of select="$html.js.root"/>
      <xsl:text>jquery.js</xsl:text>
    </xsl:attribute>
  </script>
  <xsl:if test="$html.syntax.highlight">
    <script type="text/javascript">
      <xsl:attribute name="src">
        <xsl:value-of select="$html.js.root"/>
        <xsl:text>jquery.syntax.js</xsl:text>
      </xsl:attribute>
    </script>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
html.js.content
Output JavaScript content for an HTML output page.
:Revision:version="1.0" date="2010-12-06" status="final"
$node: The node to create JavaScript for.

This template is called by *{html.js} to output JavaScript content. It does not
output an HTML #{script} tag. The JavaScript output by this template or templates
it calls may depend on the jQuery code referenced by *{html.js.jquery}. This
template calls the template *{html.js.media}. It then calls the mode
%{html.js.mode} on ${node} and calls the template *{html.js.content.custom}.
-->
<xsl:template name="html.js.content">
  <xsl:param name="node" select="."/>
  <xsl:call-template name="html.js.ui">
    <xsl:with-param name="node" select="$node"/>
  </xsl:call-template>
  <xsl:call-template name="html.js.media">
    <xsl:with-param name="node" select="$node"/>
  </xsl:call-template>
  <xsl:call-template name="html.js.syntax">
    <xsl:with-param name="node" select="$node"/>
  </xsl:call-template>
  <xsl:apply-templates mode="html.js.mode" select="$node"/>
  <xsl:call-template name="html.js.content.custom">
    <xsl:with-param name="node" select="$node"/>
  </xsl:call-template>
</xsl:template>


<!--**==========================================================================
html.js.ui
Output JavaScript for UI extensions.
:Revision: version="1.0" date="2011-06-17" status="final"
$node: The node to create JavaScript for.

This template outputs JavaScript that implements certain common UI extensions,
such as expandable blocks and sections.
-->
<xsl:template name="html.js.ui">
  <xsl:param name="node" select="."/>
<xsl:text><![CDATA[
$.fn.yelp_ui_expander_toggle = function (onlyopen) {
  var expander = $(this);
  var region = expander.children('.inner').children('.region');
  var yelpdata = expander.children('div.yelp-data-ui-expander');
  var compfunc = function () { return true; };
  if (expander.is('div.figure'))
    compfunc = function () { expander.yelp_auto_resize(); };
  var title = expander.children('.inner').children('.title');
  if (title.length == 0)
    title = expander.children('.inner').children('.hgroup');
  var title = title.find('span.title:first');
  if (expander.is('.ui-expander-e')) {
    if (!onlyopen) {
      expander.removeClass('ui-expander-e').addClass('ui-expander-c');
      region.attr('aria-expanded', 'false').slideUp('fast', compfunc);
      title.html(yelpdata.children('div.yelp-title-collapsed').html());
    }
  }
  else {
    expander.removeClass('ui-expander-c').addClass('ui-expander-e');
    region.attr('aria-expanded', 'true').slideDown('fast', compfunc);
    title.html(yelpdata.children('div.yelp-title-expanded').html());
  }
};
$(document).ready(function () {
  $('.ui-expander').each(function () {
    var expander = $(this);
    var yelpdata = expander.children('div.yelp-data-ui-expander');
    var arrow;
    if (yelpdata.attr('dir') == 'rtl')
      arrow = $('<span class="ui-expander-arrow-rtl">◂</span>');
    else
      arrow = $('<span class="ui-expander-arrow-ltr">▸</span>');
    var region = expander.children('.inner').children('.region');
    var title = expander.children('.inner').children('.title');
    var issect = false;
    if (title.length == 0) {
      title = expander.children('.inner').children('.hgroup');
      issect = true;
    }
    if (title.length == 0) {
      return;
    }
    title.attr('role', 'button').attr('aria-controls', region.attr('id'));
    if (issect) {
      title.children('.title').prepend('&#x00A0;&#x00A0;').prepend(arrow);
    } else {
      title.children().append('&#x00A0;&#x00A0;').append(arrow);
    }
    var titlespan = title.find('span.title:first');
    var title_e = yelpdata.children('div.yelp-title-expanded');
    var title_c = yelpdata.children('div.yelp-title-collapsed');
    if (title_e.length == 0)
      yelpdata.append($('<div class="yelp-title-expanded"></div>').html(titlespan.html()));
    if (title_c.length == 0)
      yelpdata.append($('<div class="yelp-title-collapsed"></div>').html(titlespan.html()));
    if (yelpdata.attr('data-yelp-expanded') == 'no') {
      expander.addClass('ui-expander-c');
      region.attr('aria-expanded', 'false').hide();
      if (title_c.length != 0)
        titlespan.html(title_c.html());
    } else {
      expander.addClass('ui-expander-e');
      region.attr('aria-expanded', 'true');
      if (title_e.length != 0)
        titlespan.html(title_e.html());
    }
    title.click(function () {
      expander.yelp_ui_expander_toggle(false);
    });
  });
});
$(document).ready(function () {
  if (location.hash != '') {
    var target = $(location.hash);
    var parents = target.parents('div.ui-expander');
    if (target.is('div.ui-expander'))
      parents = parents.andSelf();
    parents.each(function () {
      $(this).yelp_ui_expander_toggle(true);
    });
  }
});
]]></xsl:text>
</xsl:template>


<!--**==========================================================================
html.js.media
Output JavaScript to control media elements.
:Revision: version="1.0" date="2010-01-01" status="final"
$node: The node to create JavaScript for.

This template outputs JavaScript that controls media elements. It provides
control for audio and video elements as well as support for captions.
-->
<xsl:template name="html.js.media">
  <xsl:param name="node" select="."/>
<xsl:text><![CDATA[
yelp_color_text_light = ']]></xsl:text>
<xsl:value-of select="$color.text_light"/><xsl:text><![CDATA[';
yelp_color_gray_border = ']]></xsl:text>
<xsl:value-of select="$color.gray_border"/><xsl:text><![CDATA[';
yelp_paint_zoom = function (zoom, zoomed) {
  var ctxt = zoom.children('canvas')[0].getContext('2d');
  ctxt.strokeStyle = ctxt.fillStyle = yelp_color_text_light;
  ctxt.clearRect(0, 0, 10, 10);
  ctxt.strokeRect(0.5, 0.5, 9, 9);
  if (zoomed) {
    ctxt.fillRect(1, 1, 9, 4);
    ctxt.fillRect(5, 5, 4, 4);
    zoom.attr('title', zoom.attr('data-zoom-out-title'));
  }
  else {
    ctxt.fillRect(1, 5, 4, 4);
    zoom.attr('title', zoom.attr('data-zoom-in-title'));
  }
}
$.fn.yelp_auto_resize = function () {
  var fig = $(this);
  if (fig.is('img'))
    fig = fig.parents('div.figure').eq(0);
  if (fig.data('yelp-zoom-timeout') != undefined) {
    clearInterval(fig.data('yelp-zoom-timeout'));
    fig.removeData('yelp-zoom-timeout');
  }
  var imgs = fig.find('img');
  for (var i = 0; i < imgs.length; i++) {
    var img = $(imgs[i]);
    if (img.data('yelp-load-bound') == true)
      img.unbind('load', fig.yelp_auto_resize);
    if (!imgs[i].complete) {
      img.data('yelp-load-bound', true);
      img.bind('load', fig.yelp_auto_resize);
      return false;
    }
  }
  $(window).unbind('resize', yelp_resize_imgs);
  var zoom = fig.children('div.inner').children('a.zoom');
  if (fig.find('div.contents:first').is(':hidden')) {
    zoom.hide();
    return;
  }
  for (var i = 0; i < imgs.length; i++) {
    var img = $(imgs[i]);
    if (img.data('yelp-original-width') == undefined) {
      var iwidth = parseInt(img.attr('width'));
      if (!iwidth)
        iwidth = img[0].width;
      img.data('yelp-original-width', iwidth);
      var iheight = parseInt(img.attr('height'));
      if (!iheight)
        iheight = img[0].height * (iwidth / img[0].width);
      img.data('yelp-original-height', iheight);
    }
    if (img.data('yelp-original-width') > img.parent().width()) {
      if (img.data('yelp-zoomed') != true) {
        img[0].width = img.parent().width();
        img[0].height = (parseInt(img.data('yelp-original-height')) *
                         img.width() / parseInt(img.data('yelp-original-width')));
      }
      zoom.show();
    }
    else {
      img[0].width = img.data('yelp-original-width');
      img[0].height = img.data('yelp-original-height');
      zoom.hide();
    }
  }
  /* The image scaling above can cause the window to resize if it causes
   * scrollbars to disappear or reapper. Unbind the resize handler before
   * scaling the image. Don't rebind immediately, because we'll still get
   * that resize event in an idle. Rebind on the callback instead.
   */
  var reresize = function () {
    $(window).unbind('resize', reresize);
    $(window).bind('resize', yelp_resize_imgs);
  }
  $(window).bind('resize', reresize);
  return false;
};
yelp_resize_imgs = function () {
  $('div.figure img').parents('div.figure').each(function () {
    var div = $(this);
    if (div.data('yelp-zoom-timeout') == undefined)
      div.data('yelp-zoom-timeout', setTimeout(function () { div.yelp_auto_resize() }, 1));
  });
  return false;
};
$(document).ready(function () {
  $('div.figure img').parents('div.figure').each(function () {
    var fig = $(this);
    var zoom = fig.children('div.inner').children('a.zoom');
    zoom.append($('<canvas width="10" height="10"/>'));
    yelp_paint_zoom(zoom, false);
    zoom.data('yelp-zoomed', false);
    zoom.click(function () {
      var zoomed = !zoom.data('yelp-zoomed');
      zoom.data('yelp-zoomed', zoomed);
      zoom.parent().find('img').each(function () {
        var zimg = $(this);
        zimg.data('yelp-zoomed', zoomed);
        if (zoomed) {
          zimg[0].width = zimg.data('yelp-original-width');
          zimg[0].height = zimg.data('yelp-original-height');
        } else {
          zimg[0].width = zimg.parent().width();
          zimg[0].height = (parseInt(zimg.data('yelp-original-height')) *
                            zimg.width() / parseInt(zimg.data('yelp-original-width')));
        }
        yelp_paint_zoom(zoom, zoomed);
      });
      return false;
    });
  });
  yelp_resize_imgs();
  $(window).bind('resize', yelp_resize_imgs);
});
function yelp_init_video (element) {
  var video = $(element);
  video.removeAttr('controls');

  var controls = $('<div class="media-controls"></div>');
  var playControl = $('<button class="media-play"></button>').attr({
    'data-play-label': video.attr('data-play-label'),
    'data-pause-label': video.attr('data-pause-label'),
    'value': video.attr('data-play-label')
  });
  var playCanvas = $('<canvas width="20" height="20"></canvas>');
  playControl.append(playCanvas);
  var rangeCanvas = $('<canvas width="104" height="20"></canvas>');
  var rangeCanvasCtxt = rangeCanvas[0].getContext('2d');
  rangeCanvasCtxt.strokeStyle = yelp_color_gray_border;
  rangeCanvasCtxt.strokeWidth = 1;
  rangeCanvasCtxt.strokeRect(0.5, 0.5, 103, 19);
  var currentSpan = $('<span class="media-current">0:00</span>');
  controls.append(playControl, $('<div class="media-range"></div>').append(rangeCanvas), currentSpan);
  video.after(controls);

  var playCanvasCtxt = playCanvas[0].getContext('2d');
  var paintPlayButton = function () {
    playCanvasCtxt.fillStyle = yelp_color_text_light;
    playCanvasCtxt.clearRect(0, 0, 20, 20);
    playCanvasCtxt.beginPath();
    playCanvasCtxt.moveTo(5, 5);   playCanvasCtxt.lineTo(5, 15);
    playCanvasCtxt.lineTo(15, 10); playCanvasCtxt.lineTo(5, 5);
    playCanvasCtxt.fill();
  }
  var paintPauseButton = function () {
    playCanvasCtxt.fillStyle = yelp_color_text_light;
    playCanvasCtxt.clearRect(0, 0, 20, 20);
    playCanvasCtxt.beginPath();
    playCanvasCtxt.moveTo(5, 5);   playCanvasCtxt.lineTo(9, 5);
    playCanvasCtxt.lineTo(9, 15);  playCanvasCtxt.lineTo(5, 15);
    playCanvasCtxt.lineTo(5, 5);   playCanvasCtxt.fill();
    playCanvasCtxt.beginPath();
    playCanvasCtxt.moveTo(11, 5);  playCanvasCtxt.lineTo(15, 5);
    playCanvasCtxt.lineTo(15, 15); playCanvasCtxt.lineTo(11, 15);
    playCanvasCtxt.lineTo(11, 5);  playCanvasCtxt.fill();
  }
  paintPlayButton();

  var video_el = video[0];
  var mediaChange = function () {
    if (video_el.ended)
      video_el.pause()
    if (video_el.paused) {
      playControl.attr('value', playControl.attr('data-play-label'));
      paintPlayButton();
    }
    else {
      playControl.attr('value', playControl.attr('data-pause-label'));
      paintPauseButton();
    }
  }
  video_el.addEventListener('play', mediaChange, false);
  video_el.addEventListener('pause', mediaChange, false);
  video_el.addEventListener('ended', mediaChange, false);

  var playClick = function () {
    if (video_el.paused || video_el.ended)
      video_el.play();
    else
      video_el.pause();
  };
  playControl.click(playClick);

  var ttmlDiv = video.parent().children('div.media-ttml');
  var ttmlNodes = ttmlDiv.find('.media-ttml-node');

  var timeUpdate = function () {
    var pct = (element.currentTime / element.duration) * 100;
    rangeCanvasCtxt.fillStyle = yelp_color_gray_border;
    rangeCanvasCtxt.clearRect(2, 2, 100, 16);
    rangeCanvasCtxt.fillRect(2, 2, pct, 16);
    var mins = parseInt(element.currentTime / 60);
    var secs = parseInt(element.currentTime - (60 * mins))
    currentSpan.text(mins + (secs < 10 ? ':0' : ':') + secs);
    ttmlNodes.each(function () {
      var ttml = this;
      if (element.currentTime >= parseFloat(ttml.getAttribute('data-begin')) &&
          (!ttml.hasAttribute('data-end') ||
           element.currentTime < parseFloat(ttml.getAttribute('data-end')) )) {
        if (ttml.tagName == 'span')
          ttml.style.display = 'inline';
        else
          ttml.style.display = 'block';
      }
      else {
        ttml.style.display = 'none';
      }
    });
  };
  element.addEventListener('timeupdate', timeUpdate, false);

  rangeCanvas.click(function (event) {
    var pct = event.clientX - Math.floor(rangeCanvas.offset().left);
    if (pct < 0)
      pct = 0;
    if (pct > 100)
      pct = 100;
    element.currentTime = (pct / 100.0) * element.duration;
  });
};
$(document).ready(function () {
  $('video.media-block').each(function () { yelp_init_video(this) });;
});
]]></xsl:text>
</xsl:template>


<!--**==========================================================================
html.js.syntax
Output JavaScript for syntax highlighting
:Revision: version="1.0" date="2011-04-16" status="final"
$node: The node to create JavaScript for.

This template outputs JavaScript that does syntax highlighting. JavaScript
@{html.syntax.highlight} is #{true}. Note that this content just initializes
the syntax highlighting. The real work is done by #{jquery.syntax.js}, which
is included by *{html.js.syntax}.
-->
<xsl:template name="html.js.syntax">
  <xsl:param name="node" select="."/>
  <xsl:if test="$html.syntax.highlight">
<xsl:text><![CDATA[
$(document).ready( function () { jQuery.syntax({root: ']]></xsl:text>
<xsl:value-of select="$html.js.root"/><xsl:text><![CDATA[', blockLayout: 'yelp'}); });
]]></xsl:text>
  </xsl:if>
</xsl:template>


<!--%%==========================================================================
html.js.mode
Output JavaScript specific to the input format.
:Revision:version="1.0" date="2010-01-01" status="final"

This template is called by *{html.js.content} to output JavaScript specific to
the input format. Importing stylesheets may implement this for any element that
will be passed to *{html.page}. If they do not, the output HTML will only have
the common JavaScript.
-->
<xsl:template mode="html.js.mode" match="*">
</xsl:template>


<!--**==========================================================================
html.js.custom
Stub to reference custom JavaScript common to all HTML transformations.
:Stub: true
:Revision: version="1.0" date="2010-04-16" status="final"
$node: The node to create JavaScript for.

This template is a stub, called by *{html.js}. You can override this template
to reference additional external JavaScript files. If you want to include
JavaScript into the main #{script} tag instead, use *{html.js.content.custom}.
-->
<xsl:template name="html.js.custom">
  <xsl:param name="node" select="."/>
</xsl:template>


<!--**==========================================================================
html.js.content.custom
Stub to output custom JavaScript common to all HTML transformations.
:Stub: true
:Revision: version="1.0" date="2010-04-16" status="final"
$node: The node to create JavaScript for.

This template is a stub, called by *{html.js.content}. You can override this
template to provide additional JavaScript that will be used by all HTML output.
This template is called inside a #{script} tag, and is intended to include
JavaScript code in the output page. See *{html.js.custom} to include a custom
reference to an external JavaScript file.
-->
<xsl:template name="html.js.content.custom">
  <xsl:param name="node" select="."/>
</xsl:template>


<!--**==========================================================================
html.lang.attrs
Output #{lang} and #{dir} attributes.
:Revision: version="1.0" date="2010-06-10" status="final"
$node: The current element in the input document.
$parent: A parent node to take ${lang} and ${dir} from.
$lang: The language for ${node}.
$dir: The text directionality for ${node}.

This template outputs #{lang}, #{xml:lang}, or #{dir} attributes if necessary.
If ${lang} is not set, it will be taken from the #{xml:lang} or #{lang}
attribute of ${node}. If ${dir} is not set, it will be taken from the #{its:dir}
attribute of ${node} or computed based on ${lang}.

The ${parent} parameter defaults to an empty node set. If it is set to a
non-empty node set, this template will attempt to get ${lang} and ${dir} from
${parent} if they are not set on ${node}. This is occasionally useful when a
wrapper element in a source language doesn't directly create any output
elements.

This template outputs either an #{xml:lang} or a #{lang} attribute, depending
on whether @{html.xhtml} is #{true}. It only outputs an #{xml:lang} or #{lang}
attribute if $lang is non-empty. This template also outputs a #{dir} attribute
if ${dir} is non-empty.
-->
<xsl:template name="html.lang.attrs">
  <xsl:param name="node" select="."/>
  <xsl:param name="parent" select="/false"/>
  <xsl:param name="lang">
    <xsl:choose>
      <xsl:when test="$node/@xml:lang">
        <xsl:value-of select="$node/@xml:lang"/>
      </xsl:when>
      <xsl:when test="$node/@lang">
        <xsl:value-of select="$node/@lang"/>
      </xsl:when>
      <xsl:when test="$parent/@xml:lang">
        <xsl:value-of select="$parent/@xml:lang"/>
      </xsl:when>
      <xsl:when test="$parent/@lang">
        <xsl:value-of select="$parent/@lang"/>
      </xsl:when>
    </xsl:choose>
  </xsl:param>
  <xsl:param name="dir">
    <xsl:choose>
      <xsl:when test="$node/@its:dir">
        <xsl:value-of select="$node/@its:dir"/>
      </xsl:when>
      <xsl:when test="($node/@xml:lang or $node/@lang) and (string($lang) != '')">
        <xsl:call-template name="l10n.direction">
          <xsl:with-param name="lang" select="$lang"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$parent/@its:dir">
        <xsl:value-of select="$node/@its:dir"/>
      </xsl:when>
      <xsl:when test="string($lang) != ''">
        <xsl:call-template name="l10n.direction">
          <xsl:with-param name="lang" select="$lang"/>
        </xsl:call-template>
      </xsl:when>
    </xsl:choose>
  </xsl:param>
  <xsl:if test="string($lang) != ''">
    <xsl:choose>
      <xsl:when test="$html.xhtml">
        <xsl:attribute name="xml:lang">
          <xsl:value-of select="$lang"/>
        </xsl:attribute>
      </xsl:when>
      <xsl:otherwise>
        <xsl:attribute name="lang">
          <xsl:value-of select="$lang"/>
        </xsl:attribute>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:if>
  <xsl:if test="string($dir) != ''">
    <xsl:attribute name="dir">
      <xsl:value-of select="$dir"/>
    </xsl:attribute>
  </xsl:if>
</xsl:template>

</xsl:stylesheet>
