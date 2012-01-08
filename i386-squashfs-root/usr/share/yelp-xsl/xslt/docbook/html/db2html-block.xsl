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
along with this program; see the file COPYING.LGPL.  If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
02111-1307, USA.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:db="http://docbook.org/ns/docbook"
                xmlns:msg="http://projects.gnome.org/yelp/gettext/"
                xmlns:set="http://exslt.org/sets"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="db msg set"
                version="1.0">

<!--!!==========================================================================
DocBook to HTML - Block Elements
:Requires: db-chunk db-common db-xref db2html-xref gettext html utils
:Revision:version="1.0" date="2011-05-12" status="final"

This module handles most simple block-level elements, turning them into the
appropriate HTML tags.  It does not handle tables, lists, and various other
complex block-level elements.
-->


<!--**==========================================================================
db2html.block
Output an HTML #{div} elements for a block-level element.
:Revision:version="1.0" date="2011-05-12" status="final"
$node: The block-level element to render.
$class: An extra string to insert in the #{class} attribute.
$verbatim: Whether to maintain whitespace as written.
$formal: Whether this is a formal block element.
$title: When ${formal} is true, an element to use for the title.
$caption: When ${formal} is true, an element to use for the caption.
$titleattr: An optional value for the HTML #{title} attribute.

This template creates an HTML #{div} element for the given DocBook element.
This template uses the parameters to construct the #{class} attribute, which
is then used by the CSS for styling.

If ${formal} is #{true}, the ${title} and ${caption} parameters are processed,
and extra container #{div} elements are output for styling.

If ${verbatim} is #{true}, the #{div} is marked with the #{verbatim} class,
which maintains whitespace. This is not the same as outputting a #{pre} tag,
which is what *{db2html.pre} does. Verbatim text from this template is not
formatted with a fixed-width font.
-->
<xsl:template name="db2html.block">
  <xsl:param name="node" select="."/>
  <xsl:param name="class" select="''"/>
	<xsl:param name="verbatim" select="$node[@xml:space = 'preserve']"/>
  <xsl:param name="formal" select="false()"/>
  <xsl:param name="title" select="$node/title | $node/db:title |
                                  $node/db:info/db:title"/>
  <xsl:param name="caption" select="$node/caption | $node/db:caption"/>
  <xsl:param name="titleattr" select="''"/>

  <div>
    <xsl:attribute name="class">
      <xsl:value-of select="concat($class, ' ', local-name($node))"/>
      <xsl:if test="$verbatim">
        <xsl:text> verbatim</xsl:text>
      </xsl:if>
    </xsl:attribute>
    <xsl:if test="$titleattr != ''">
      <xsl:attribute name="title">
        <xsl:value-of select="$titleattr"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:call-template name="html.lang.attrs">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
    <xsl:call-template name="db2html.anchor">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
    <xsl:choose>
      <xsl:when test="$formal">
        <div class="inner">
          <xsl:if test="$node/self::figure or $node/self::db:figure">
            <a href="#" class="zoom">
              <xsl:attribute name="data-zoom-in-title">
                <xsl:call-template name="l10n.gettext">
                  <xsl:with-param name="msgid" select="'View images at normal size'"/>
                </xsl:call-template>
              </xsl:attribute>
              <xsl:attribute name="data-zoom-out-title">
                <xsl:call-template name="l10n.gettext">
                  <xsl:with-param name="msgid" select="'Scale images down'"/>
                </xsl:call-template>
              </xsl:attribute>
            </a>
          </xsl:if>
          <xsl:if test="$title">
            <xsl:call-template name="db2html.block.title">
              <xsl:with-param name="node" select="$node"/>
              <xsl:with-param name="title" select="$title"/>
            </xsl:call-template>
          </xsl:if>
          <div class="region">
            <div class="contents">
              <xsl:apply-templates select="$node/node()[not(set:has-same-node(., $title | $caption))]"/>
            </div>
            <xsl:apply-templates select="$caption"/>
          </div>
        </div>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates select="$node/node()"/>
      </xsl:otherwise>
    </xsl:choose>
  </div>
</xsl:template>


<!--**==========================================================================
db2html.block.title
Render a formal title for a block-level element.
:Revision:version="1.0" date="2011-05-12" status="final"
$node: The block-level element being processed.
$title: The element containing the title.

This template formats the contents of ${title} as a title for a block-level
element.  It is called by *{db2html.block} for formal block elements.
-->
<xsl:template name="db2html.block.title">
  <xsl:param name="node" select="."/>
	<xsl:param name="title" select="$node/title | $node/db:title"/>
  <xsl:variable name="depth">
    <xsl:call-template name="db.chunk.depth-in-chunk">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:variable name="depth_">
    <xsl:choose>
      <xsl:when test="number($depth) &lt; 6">
        <xsl:value-of select="number($depth) + 1"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="6"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <div class="title">
    <xsl:call-template name="html.lang.attrs">
      <xsl:with-param name="node" select="$title"/>
    </xsl:call-template>
    <xsl:call-template name="db2html.anchor">
      <xsl:with-param name="node" select="$title"/>
    </xsl:call-template>
    <xsl:element name="{concat('h', $depth_)}" namespace="{$html.namespace}">
      <span class="title">
        <xsl:apply-templates select="$title/node()"/>
      </span>
    </xsl:element>
  </div>
</xsl:template>


<!--**==========================================================================
db2html.blockquote
Output an HTML #{blockquote} element.
:Revision:version="1.0" date="2011-05-12" status="final"
$node: The #{blockquote} element to render.

This template creates an HTML #{blockquote} element for the given DocBook
element.
-->
<xsl:template name="db2html.blockquote">
  <xsl:param name="node" select="."/>
  <div>
    <xsl:attribute name="class">
      <xsl:text>quote </xsl:text>
      <xsl:value-of select="local-name($node)"/>
    </xsl:attribute>
    <xsl:call-template name="html.lang.attrs">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
    <xsl:call-template name="db2html.anchor">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
    <div class="inner">
      <xsl:apply-templates select="$node/title | $node/db:title |
                                   $node/db:info/db:title"/>
      <div class="region">
        <blockquote class="{local-name($node)}">
          <xsl:apply-templates select="$node/node()[not(self::title) and not(self::attribution) and not(self::db:title) and not(self::db:attribution)]"/>
        </blockquote>
        <xsl:apply-templates select="$node/attribution | $node/db:attribution"/>
      </div>
    </div>
  </div>
</xsl:template>


<!--**==========================================================================
db2html.para
Output an HTML #{p} element for a block-level element.
:Revision:version="1.0" date="2011-05-12" status="final"
$node: The block-level element to render.
$class: The value of the HTMl #{class} attribute.

This template creates an HTML #{p} element for the given DocBook element.
-->
<xsl:template name="db2html.para">
  <xsl:param name="node" select="."/>
  <xsl:param name="class" select="local-name($node)"/>
  <p>
    <xsl:attribute name="class">
      <xsl:value-of select="$class"/>
    </xsl:attribute>
    <xsl:call-template name="html.lang.attrs">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
    <xsl:call-template name="db2html.anchor">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
    <xsl:apply-templates select="$node/node()"/>
  </p>
</xsl:template>


<!--**==========================================================================
db2html.pre
Output and HTML #{pre} elements for a block-level element.
$node: The block-level element to render.
$class: An extra string to insert in the #{class} attribute.
$children: The child elements to process.

This template creates an HTML #{pre} element for the given DocBook element.
This template uses the parameters to construct the #{class} attribute, which
is then used by the CSS for styling.

If ${node} has the #{linenumbering} attribute set to #{"numbered"}, then this
template will create line numbers for each line, using the *{utils.linenumbering}
template.

By default, this template applies templates to all child nodes. Pass child
nodes in the ${children} parameter to override this behavior.

If @{html.syntax.highlight} is #{true}, this template automatically outputs
syntax highlighting support based on the #{language} attribute of ${node}.
-->
<xsl:template name="db2html.pre">
  <xsl:param name="node" select="."/>
  <xsl:param name="class" select="''"/>
  <xsl:param name="children" select="$node/node()"/>

  <div>
    <xsl:attribute name="class">
      <xsl:value-of select="concat($class, ' ', local-name($node))"/>
    </xsl:attribute>
    <xsl:call-template name="html.lang.attrs">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
    <xsl:call-template name="db2html.anchor">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
    <xsl:if test="$node/@linenumbering = 'numbered'">
      <xsl:variable name="number">
        <xsl:choose>
          <xsl:when test="@startinglinenumber">
            <xsl:value-of select="@startinglinenumber"/>
          </xsl:when>
          <xsl:when test="@continuation">
            <xsl:call-template name="db.linenumbering.start">
              <xsl:with-param name="node" select="$node"/>
            </xsl:call-template>
          </xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </xsl:variable>
      <pre class="numbered"><xsl:call-template name="utils.linenumbering">
        <xsl:with-param name="node" select="$node"/>
        <xsl:with-param name="number" select="$number"/>
      </xsl:call-template></pre>
    </xsl:if>
    <pre>
      <xsl:attribute name="class">
        <xsl:text>contents </xsl:text>
        <xsl:if test="$html.syntax.highlight and $node/@language">
          <xsl:choose>
            <xsl:when test="@language = 'bash'">
              <xsl:text>syntax brush-bash-script</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'c' or @language = 'cpp' or @language = 'objc'">
              <xsl:text>syntax brush-clang</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'csharp'">
              <xsl:text>syntax brush-csharp</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'css'">
              <xsl:text>syntax brush-css</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'diff'">
              <xsl:text>syntax brush-diff</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'html' or @language = 'xml'">
              <xsl:text>syntax brush-html</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'java'">
              <xsl:text>syntax brush-java</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'javascript'">
              <xsl:text>syntax brush-javascript</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'lisp'">
              <xsl:text>syntax brush-lisp</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'lua'">
              <xsl:text>syntax brush-lua</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'pascal'">
              <xsl:text>syntax brush-pascal</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'perl'">
              <xsl:text>syntax brush-perl5</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'php'">
              <xsl:text>syntax brush-php-script</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'python'">
              <xsl:text>syntax brush-python</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'ruby'">
              <xsl:text>syntax brush-ruby</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'sql'">
              <xsl:text>syntax brush-sql</xsl:text>
            </xsl:when>
            <xsl:when test="@language = 'yaml'">
              <xsl:text>syntax brush-yaml</xsl:text>
            </xsl:when>
          </xsl:choose>
        </xsl:if>
      </xsl:attribute>
      <!-- Strip off a leading newline -->
      <xsl:if test="$children[1]/self::text()">
        <xsl:choose>
          <xsl:when test="starts-with($node/text()[1], '&#x000A;')">
            <xsl:value-of select="substring-after($node/text()[1], '&#x000A;')"/>
          </xsl:when>
          <xsl:otherwise>
            <xsl:value-of select="$node/text()[1]"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:if>
      <xsl:apply-templates select="$children[not(position() = 1 and self::text())]"/>
    </pre>
  </div>
</xsl:template>


<!-- == Matched Templates == -->

<!-- = abstract = -->
<xsl:template match="abstract | db:abstract">
  <xsl:call-template name="db2html.block"/>
</xsl:template>

<!-- = ackno = -->
<xsl:template match="ackno | db:acknowledgements/db:para">
  <xsl:call-template name="db2html.para">
    <xsl:with-param name="class" select="'ackno'"/>
  </xsl:call-template>
</xsl:template>

<!-- = address = -->
<xsl:template match="address | db:address">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="verbatim" select="true()"/>
  </xsl:call-template>
</xsl:template>

<!-- = attribution = -->
<xsl:template match="attribution | db:attribution">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="class" select="'cite'"/>
  </xsl:call-template>
</xsl:template>

<!-- = blockquote = -->
<xsl:template match="blockquote | db:blockquote">
  <xsl:call-template name="db2html.blockquote"/>
</xsl:template>

<!-- = caption = -->
<xsl:template match="caption | db:caption">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="class" select="'desc'"/>
  </xsl:call-template>
</xsl:template>

<!-- = caution = -->
<xsl:template match="caution | db:caution">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="class" select="'note note-warning'"/>
    <xsl:with-param name="formal" select="true()"/>
    <xsl:with-param name="titleattr">
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="'Warning'"/>
      </xsl:call-template>
    </xsl:with-param>
  </xsl:call-template>
</xsl:template>

<!-- = epigraph = -->
<xsl:template match="epigraph | db:epigraph">
  <xsl:call-template name="db2html.blockquote"/>
</xsl:template>

<!-- = equation = -->
<xsl:template match="equation | db:equation">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="formal" select="true()"/>
  </xsl:call-template>
</xsl:template>

<!-- = example = -->
<xsl:template match="example | db:example">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="formal" select="true()"/>
  </xsl:call-template>
</xsl:template>

<!-- = figure = -->
<xsl:template match="figure | informalfigure | db:figure | db:informalfigure">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="class">
      <xsl:if test="self::informalfigure | self::db:informalfigure">
        <xsl:text>figure</xsl:text>
      </xsl:if>
    </xsl:with-param>
    <xsl:with-param name="formal" select="true()"/>
    <!-- When a figure contains only a single mediaobject, it eats the caption -->
    <xsl:with-param name="caption"
                    select="*[not(self::blockinfo) and not(self::title) and not(self::titleabbrev)]
														[last() = 1]/self::mediaobject/caption |
														*[not(self::db:info) and not(self::db:title) and not(self::db:titleabbrev)]
                            [last() = 1]/self::db:mediaobject/db:caption"/>
  </xsl:call-template>
</xsl:template>

<!-- = formalpara = -->
<xsl:template match="formalpara | db:formalpara">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="formal" select="true()"/>
  </xsl:call-template>
</xsl:template>

<!-- = glossdef = -->
<xsl:template match="glossdef | db:glossdef">
  <dd class="glossdef">
    <xsl:apply-templates select="*[not(self::glossseealso) and not(self::db:glossseealso)]"/>
  </dd>
  <xsl:apply-templates select="glossseealso[1] | db:glossseealso[1]"/>
</xsl:template>

<!-- = glossentry = -->
<xsl:template match="glossentry | db:glossentry">
  <dt>
    <xsl:attribute name="class">
      <xsl:text>glossterm</xsl:text>
    </xsl:attribute>
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates select="glossterm | db:glossterm"/>
    <xsl:if test="acronym or abbrev or db:acronym or db:abbrev">
      <xsl:text> (</xsl:text>
      <xsl:apply-templates select="(acronym | abbrev | db:acronym | db:abbrev)[1]"/>
      <xsl:text>)</xsl:text>
    </xsl:if>
  </dt>
  <xsl:apply-templates select="glossdef | glosssee[1] | db:glossdef | db:glosssee[1]"/>
</xsl:template>

<!-- = glosssee(also) = -->
<xsl:template match="glosssee | glossseealso | db:glosssee | db:glossseealso">
  <dd class="{local-name(.)}">
    <p>
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="concat(local-name(.), '.format')"/>
        <xsl:with-param name="node" select="."/>
        <xsl:with-param name="format" select="true()"/>
      </xsl:call-template>
    </p>
  </dd>
</xsl:template>

<!--#% l10n.format.mode -->
<xsl:template mode="l10n.format.mode" match="msg:glosssee">
  <xsl:param name="node"/>
  <xsl:for-each select="$node |
                        $node/following-sibling::*[name(.) = name($node)]">
    <xsl:if test="position() != 1">
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="', '"/>
      </xsl:call-template>
    </xsl:if>
    <xsl:choose>
      <xsl:when test="@otherterm">
        <a>
          <xsl:attribute name="href">
            <xsl:call-template name="db.xref.target">
              <xsl:with-param name="linkend" select="@otherterm"/>
            </xsl:call-template>
          </xsl:attribute>
          <xsl:attribute name="title">
            <xsl:call-template name="db.xref.tooltip">
              <xsl:with-param name="linkend" select="@otherterm"/>
            </xsl:call-template>
          </xsl:attribute>
          <xsl:choose>
            <xsl:when test="normalize-space(.) != ''">
              <xsl:apply-templates/>
            </xsl:when>
            <xsl:otherwise>
              <xsl:call-template name="db.xref.content">
                <xsl:with-param name="linkend" select="@otherterm"/>
                <xsl:with-param name="role" select="'glosssee'"/>
              </xsl:call-template>
            </xsl:otherwise>
          </xsl:choose>
        </a>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:for-each>
</xsl:template>

<!-- = highlights = -->
<xsl:template match="highlights">
  <xsl:call-template name="db2html.block"/>
</xsl:template>

<!-- = important = -->
<xsl:template match="important | db:important">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="class" select="'note note-important'"/>
    <xsl:with-param name="formal" select="true()"/>
    <xsl:with-param name="titleattr">
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="'Important'"/>
      </xsl:call-template>
    </xsl:with-param>
  </xsl:call-template>
</xsl:template>

<!-- = informalequation = -->
<xsl:template match="informalequation | db:informalequation">
  <xsl:call-template name="db2html.block"/>
</xsl:template>

<!-- = informalexample = -->
<xsl:template match="informalexample | db:informalexample">
  <xsl:call-template name="db2html.block"/>
</xsl:template>

<!-- = literallayout = -->
<xsl:template match="literallayout | db:literallayout">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="verbatim" select="true()"/>
  </xsl:call-template>
</xsl:template>

<!-- = note = -->
<xsl:template match="note | db:note">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="class">
      <xsl:text>note</xsl:text>
      <xsl:if test="@role = 'bug'">
        <xsl:text> note-bug</xsl:text>
      </xsl:if>
    </xsl:with-param>
    <xsl:with-param name="formal" select="true()"/>
    <xsl:with-param name="titleattr">
      <xsl:choose>
        <xsl:when test="@role = 'bug'">
          <xsl:call-template name="l10n.gettext">
            <xsl:with-param name="msgid" select="'Bug'"/>
          </xsl:call-template>
        </xsl:when>
        <xsl:otherwise>
          <xsl:call-template name="l10n.gettext">
            <xsl:with-param name="msgid" select="'Note'"/>
          </xsl:call-template>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:with-param>
  </xsl:call-template>
</xsl:template>

<!-- = para = -->
<xsl:template match="para | db:para">
  <xsl:call-template name="db2html.para"/>
</xsl:template>

<!-- = programlisting = -->
<xsl:template match="programlisting | db:programlisting">
  <xsl:call-template name="db2html.pre">
    <xsl:with-param name="class" select="'code'"/>
  </xsl:call-template>
</xsl:template>

<!-- = screen = -->
<xsl:template match="screen | db:screen">
  <xsl:call-template name="db2html.pre"/>
</xsl:template>

<!-- = simpara = -->
<xsl:template match="simpara | db:simpara">
  <xsl:call-template name="db2html.para"/>
</xsl:template>

<!-- = synopsis = -->
<xsl:template match="synopsis | db:synopsis">
  <xsl:call-template name="db2html.pre"/>
</xsl:template>

<!-- = tip = -->
<xsl:template match="tip | db:tip">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="class" select="'note note-tip'"/>
    <xsl:with-param name="formal" select="true()"/>
    <xsl:with-param name="titleattr">
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="'Tip'"/>
      </xsl:call-template>
    </xsl:with-param>
  </xsl:call-template>
</xsl:template>

<!-- = title = -->
<xsl:template match="title | db:title">
  <xsl:call-template name="db2html.block.title">
    <xsl:with-param name="node" select=".."/>
    <xsl:with-param name="title" select="."/>
  </xsl:call-template>
</xsl:template>

<!-- = warning = -->
<xsl:template match="warning | db:warning">
  <xsl:call-template name="db2html.block">
    <xsl:with-param name="class" select="'note note-warning'"/>
    <xsl:with-param name="formal" select="true()"/>
    <xsl:with-param name="titleattr">
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="'Warning'"/>
      </xsl:call-template>
    </xsl:with-param>
  </xsl:call-template>
</xsl:template>

</xsl:stylesheet>
