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
                xmlns:set="http://exslt.org/sets"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="db set"
                version="1.0">

<!--!!==========================================================================
DocBook to HTML - Divisions
:Requires: db-chunk db-title db-xref db2html-autotoc db2html-css db2html-footnote db2html-info db2html-xref gettext

REMARK: Describe this module
-->


<xsl:template mode="html.title.mode" match="*">
  <xsl:variable name="title">
    <xsl:call-template name="db.title">
      <xsl:with-param name="node" select="."/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:value-of select="normalize-space($title)"/>
</xsl:template>

<xsl:template mode="html.header.mode" match="*">
  <xsl:call-template name="db2html.linktrail"/>
</xsl:template>

<xsl:template mode="html.body.mode" match="*">
  <xsl:call-template name="db2html.links.next"/>
  <xsl:choose>
    <xsl:when test="self::db:info or self::bookinfo or self::articleinfo">
      <!-- FIXME
      <xsl:call-template name="db2html.info.div">
        <xsl:with-param name="node" select=".."/>
        <xsl:with-param name="info" select="."/>
      </xsl:call-template>
      -->
    </xsl:when>
    <xsl:otherwise>
      <xsl:apply-templates select=".">
        <xsl:with-param name="depth_in_chunk" select="0"/>
      </xsl:apply-templates>
    </xsl:otherwise>
  </xsl:choose>
  <xsl:call-template name="db2html.links.next"/>
  <div class="clear"/>
</xsl:template>

<xsl:template mode="html.output.after.mode" match="*">
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:if test="count(ancestor::*) &lt; $db.chunk.max_depth">
    <xsl:for-each select="appendix     | db:appendix     | article    | db:article    |
                          bibliography | db:bibliography | bibliodiv  | db:bibliodiv  |
                          book         | db:book         | chapter    | db:chapter    |
                          colophon     | db:colophon     | dedication | db:dedication |
                          glossary     | db:glossary     | glossdiv   | db:glossdiv   |
                          index        | db:index        | lot        | db:lot        |
                          part         | db:part         | preface    | db:preface    |
                          refentry     | db:refentry     | reference  | db:reference  |
                          sect1    | sect2    | sect3    | sect4    | sect5    | section    |
                          db:sect1 | db:sect2 | db:sect3 | db:sect4 | db:sect5 | db:section |
                          setindex     | db:setindex     | simplesect | db:simplesect |
                          toc          | db:toc          ">
      <xsl:call-template name="html.output">
        <xsl:with-param name="node" select="."/>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:if>
  <xsl:if test="$db.chunk.info_chunk and $depth_of_chunk = 0 and
                (local-name(.) = 'book' or local-name(.) = 'article')">
    <xsl:call-template name="html.output">
      <xsl:with-param name="node" select="bookinfo | articleinfo | db:info"/>
    </xsl:call-template>
  </xsl:if>
</xsl:template>


<!--FIXME
@@==========================================================================
db2html.sidenav
Whether to create a navigation sidebar

This boolean parameter specifies whether a full navigation tree in a sidebar.
The navigation sidebar is inserted by *{db2html.division.sidebar}, so this
parameter may have no effect if that template has been overridden.
-->
<xsl:param name="FIXME.db2html.sidenav" select="true()"/>


<!--**==========================================================================
db2html.division.div
Renders the content of a division element, chunking children if necessary
$node: The element to render the content of
$info: The info child element of ${node}
$title_node: The element containing the title of ${node}
$subtitle_node: The element containing the subtitle of ${node}
$title_content: The title for divisions lacking a #{title} tag
$subtitle_content: The subtitle for divisions lacking a #{subtitle} tag
$entries: The entry-style child elements
$divisions: The division-level child elements
$callback: Whether to process ${node} in %{db2html.division.div.content.mode}
$depth_in_chunk: The depth of ${node} in the containing chunk
$depth_of_chunk: The depth of the containing chunk in the document
$chunk_divisions: Whether to create new documents for ${divisions}
$chunk_info: Whether to create a new document for a title page
$autotoc_depth: How deep to create contents listings of ${divisions}
$lang: The locale of the text in ${node}
$dir: The text direction, either #{ltr} or #{rtl}

REMARK: Talk about some of the parameters
-->
<xsl:template name="db2html.division.div">
  <xsl:param name="node" select="."/>
  <xsl:param name="info" select="/false"/>
  <xsl:param name="title_node"
             select="($node/title | $info/title | $node/db:title | $info/db:title)[last()]"/>
  <xsl:param name="subtitle_node"
             select="($node/subtitle | $info/subtitle | $node/db:subtitle | $info/db:subtitle)[last()]"/>
  <xsl:param name="title_content"/>
  <xsl:param name="subtitle_content"/>
  <xsl:param name="entries" select="/false"/>
  <xsl:param name="divisions" select="/false"/>
  <xsl:param name="callback" select="false()"/>
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:param>
  <!-- FIXME: these two parameters don't make much sense now -->
  <xsl:param name="chunk_divisions"
             select="($depth_in_chunk = 0) and
                     ($depth_of_chunk &lt; $db.chunk.max_depth)"/>
  <xsl:param name="chunk_info"
             select="($depth_of_chunk = 0) and
                     ($depth_in_chunk = 0 and $info)"/>
  <xsl:param name="autotoc_depth" select="number(boolean($divisions))"/>
  <xsl:param name="lang" select="$node/@lang | $node/@xml:lang"/>
  <xsl:param name="dir" select="false()"/>

  <div>
    <xsl:attribute name="class">
      <xsl:value-of select="local-name($node)"/>
      <xsl:choose>
        <xsl:when test="$depth_in_chunk = 0">
          <xsl:text> contents</xsl:text>
        </xsl:when>
        <xsl:otherwise>
          <xsl:text> sect</xsl:text>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:attribute>
    <xsl:choose>
      <xsl:when test="$dir = 'ltr' or $dir = 'rtl'">
        <xsl:attribute name="dir">
          <xsl:value-of select="$dir"/>
        </xsl:attribute>
      </xsl:when>
      <xsl:when test="$lang">
        <xsl:attribute name="dir">
          <xsl:call-template name="l10n.direction">
            <xsl:with-param name="lang" select="$lang"/>
          </xsl:call-template>
        </xsl:attribute>
      </xsl:when>
    </xsl:choose>
    <xsl:if test="$node/@id">
      <xsl:attribute name="id">
        <xsl:value-of select="$node/@id"/>
      </xsl:attribute>
    </xsl:if>
    <div class="inner">
    <xsl:call-template name="db2html.hgroup">
      <xsl:with-param name="node" select="$node"/>
      <xsl:with-param name="title_node" select="$title_node"/>
      <xsl:with-param name="subtitle_node" select="$subtitle_node"/>
      <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
      <xsl:with-param name="title_content" select="$title_content"/>
      <xsl:with-param name="subtitle_content" select="$subtitle_content"/>
    </xsl:call-template>
    <div class="region">
    <xsl:choose>
      <xsl:when test="$callback">
        <xsl:apply-templates mode="db2html.division.div.content.mode" select="$node">
          <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
          <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
        </xsl:apply-templates>
      </xsl:when>
      <xsl:otherwise>
        <xsl:variable name="nots" select="$divisions | $entries | $title_node | $subtitle_node"/>
        <xsl:apply-templates select="*[not(set:has-same-node(., $nots))]">
          <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk + 1"/>
          <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
        </xsl:apply-templates>
        <xsl:if test="$entries">
          <div class="block">
            <dl class="{local-name($node)}">
              <xsl:apply-templates select="$entries">
                <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk + 1"/>
                <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
              </xsl:apply-templates>
            </dl>
          </div>
        </xsl:if>
      </xsl:otherwise>
    </xsl:choose>
    <xsl:if test="$autotoc_depth != 0 and
                  not($node/processing-instruction('db2html.no_sectionlinks'))">
      <xsl:call-template name="db2html.autotoc">
        <xsl:with-param name="node" select="$node"/>
        <xsl:with-param name="title" select="true()"/>
        <xsl:with-param name="divisions" select="$divisions"/>
        <xsl:with-param name="toc_depth" select="$autotoc_depth"/>
        <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
      </xsl:call-template>
    </xsl:if>
    <xsl:if test="not($chunk_divisions)">
      <xsl:apply-templates select="$divisions">
        <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk + 1"/>
        <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
      </xsl:apply-templates>
    </xsl:if>
    <xsl:if test="$depth_in_chunk = 0">
      <xsl:call-template name="db2html.footnote.footer">
        <xsl:with-param name="node" select="$node"/>
        <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
      </xsl:call-template>
    </xsl:if>
  </div>
  </div>
  </div>
</xsl:template>


<!--%%==========================================================================
db2html.division.div.content.mode
Renders the block-level content of a division element
$depth_in_chunk: The depth of the context element in the containing chunk
$depth_of_chunk: The depth of the containing chunk in the document

REMARK: Talk about how this works with #{callback}
-->
<xsl:template mode="db2html.division.div.content.mode" match="*"/>


<!--**==========================================================================
db2html.hgroup
Output the title and subtitle for an element.
$node: The element containing the title.
$title_node: The #{title} element to render.
$subtitle_node: The #{subtitle} element to render.
$depth: The depth of ${node} in the containing output.
$title_content: An optional string containing the title.
$subtitle_content: An optional string containing the subtitle.

REMARK: Talk about the different kinds of title blocks
-->
<xsl:template name="db2html.hgroup">
  <xsl:param name="node" select="."/>
  <xsl:param name="title_node" select="($node/title | $node/db:title | $node/db:info/db:title)[1]"/>
  <xsl:param name="subtitle_node" select="($node/subtitle | $node/db:subtitle | $node/db:info/db:subtitle)[1]"/>
  <xsl:param name="depth">
    <xsl:call-template name="db.chunk.depth-in-chunk">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="title_content"/>
  <xsl:param name="subtitle_content"/>

  <xsl:variable name="title_h">
    <xsl:choose>
      <xsl:when test="$depth &lt; 6">
        <xsl:value-of select="concat('h', $depth + 1)"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:text>h6</xsl:text>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <xsl:variable name="subtitle_h">
    <xsl:choose>
      <xsl:when test="$depth &lt; 5">
        <xsl:value-of select="concat('h', $depth + 2)"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:text>h6</xsl:text>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>

  <div class="hgroup">
    <xsl:element name="{$title_h}" namespace="{$html.namespace}">
      <xsl:attribute name="class">
        <xsl:text>title</xsl:text>
      </xsl:attribute>
      <xsl:if test="$title_node">
        <xsl:call-template name="db2html.anchor">
          <xsl:with-param name="node" select="$title_node"/>
        </xsl:call-template>
      </xsl:if>
      <xsl:choose>
        <xsl:when test="$title_content">
          <xsl:value-of select="$title_content"/>
        </xsl:when>
        <xsl:otherwise>
          <xsl:apply-templates select="$title_node/node()"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:element>
    <xsl:if test="$subtitle_node or $subtitle_content">
      <xsl:element name="{$subtitle_h}" namespace="{$html.namespace}">
        <xsl:attribute name="class">
          <xsl:text>subtitle</xsl:text>
        </xsl:attribute>
        <xsl:choose>
          <xsl:when test="$subtitle_content">
            <xsl:value-of select="$subtitle_content"/>
          </xsl:when>
          <xsl:otherwise>
            <xsl:apply-templates select="$subtitle_node/node()"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:element>
    </xsl:if>
  </div>
</xsl:template>


<!--**==========================================================================
db2html.linktrail
Generates links to pages from ancestor elements
$node: The element to generate links for

REMARK: Describe this
-->
<xsl:template name="db2html.linktrail">
  <xsl:param name="node" select="."/>
  <xsl:if test="$node/ancestor::*">
    <div class="trails">
      <div class="trail">
        <!-- The parens put the nodes back in document order -->
        <xsl:for-each select="($node/ancestor::*)">
          <a class="trail">
            <xsl:attribute name="href">
              <xsl:call-template name="db.xref.target">
                <xsl:with-param name="linkend" select="@id | @xml:id"/>
                <xsl:with-param name="target" select="."/>
                <xsl:with-param name="is_chunk" select="true()"/>
              </xsl:call-template>
            </xsl:attribute>
            <xsl:attribute name="title">
              <xsl:call-template name="db.xref.tooltip">
                <xsl:with-param name="linkend" select="@id | @xml:id"/>
                <xsl:with-param name="target" select="."/>
              </xsl:call-template>
            </xsl:attribute>
            <xsl:call-template name="db.titleabbrev">
              <xsl:with-param name="node" select="."/>
            </xsl:call-template>
          </a>
          <xsl:text>&#x00A0;» </xsl:text>
        </xsl:for-each>
      </div>
    </div>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
db2html.links.next
Generates navigation links for a page
$node: The element to generate links for
$prev_id: The id of the previous page
$next_id: The id of the next page
$prev_node: The element of the previous page
$next_node: The element of the next page
$position: Where the block is positioned on the pages, either 'top' or 'bottom'

REMARK: Document this template
-->
<xsl:template name="db2html.links.next">
  <xsl:param name="node" select="."/>
  <xsl:param name="info" select="/false"/>
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="prev_id">
    <xsl:choose>
      <xsl:when test="$depth_of_chunk = 0">
        <xsl:if test="$info and $db.chunk.info_chunk">
          <xsl:value-of select="$db.chunk.info_basename"/>
        </xsl:if>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="db.chunk.chunk-id.axis">
          <xsl:with-param name="node" select="$node"/>
          <xsl:with-param name="axis" select="'previous'"/>
          <xsl:with-param name="depth_in_chunk" select="0"/>
          <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:param>
  <xsl:param name="next_id">
    <xsl:call-template name="db.chunk.chunk-id.axis">
      <xsl:with-param name="node" select="$node"/>
      <xsl:with-param name="axis" select="'next'"/>
      <xsl:with-param name="depth_in_chunk" select="0"/>
      <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="prev_node" select="key('idkey', $prev_id)"/>
  <xsl:param name="next_node" select="key('idkey', $next_id)"/>
  <div class="links nextlinks">
    <xsl:if test="$prev_id != ''">
      <a class="nextlinks-prev">
        <xsl:attribute name="href">
          <xsl:call-template name="db.xref.target">
            <xsl:with-param name="linkend" select="$prev_id"/>
            <xsl:with-param name="target" select="$prev_node"/>
            <xsl:with-param name="is_chunk" select="true()"/>
          </xsl:call-template>
        </xsl:attribute>
        <xsl:choose>
          <xsl:when test="$prev_id = $db.chunk.info_basename">
            <xsl:variable name="text">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'About This Document'"/>
              </xsl:call-template>
            </xsl:variable>
            <xsl:attribute name="title">
              <xsl:value-of select="$text"/>
            </xsl:attribute>
            <xsl:value-of select="$text"/>
          </xsl:when>
          <xsl:otherwise>
            <xsl:attribute name="title">
              <xsl:call-template name="db.xref.tooltip">
                <xsl:with-param name="linkend" select="$prev_id"/>
                <xsl:with-param name="target" select="$prev_node"/>
              </xsl:call-template>
            </xsl:attribute>
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="'Previous'"/>
            </xsl:call-template>
          </xsl:otherwise>
        </xsl:choose>
      </a>
    </xsl:if>
    <xsl:if test="$prev_id != '' and $next_id != ''">
      <xsl:text>&#x00A0;&#x00A0;|&#x00A0;&#x00A0;</xsl:text>
    </xsl:if>
    <xsl:if test="$next_id != ''">
      <a class="nextlinks-next">
        <xsl:attribute name="href">
          <xsl:call-template name="db.xref.target">
            <xsl:with-param name="linkend" select="$next_id"/>
            <xsl:with-param name="is_chunk" select="true()"/>
          </xsl:call-template>
        </xsl:attribute>
        <xsl:attribute name="title">
          <xsl:call-template name="db.xref.tooltip">
            <xsl:with-param name="linkend" select="$next_id"/>
            <xsl:with-param name="target"  select="$next_node"/>
          </xsl:call-template>
        </xsl:attribute>
        <xsl:call-template name="l10n.gettext">
          <xsl:with-param name="msgid" select="'Next'"/>
        </xsl:call-template>
      </a>
    </xsl:if>
  </div>
</xsl:template>


<!--**==========================================================================
db2html.sidenav
Generates a navigation sidebar
$node: The currently-selected division element
$template: The named template to call to create the page

REMARK: Document this template
-->
<xsl:template name="db2html.sidenav">
  <xsl:param name="node" select="."/>
  <xsl:param name="template"/>
  <div class="sidenav">
    <xsl:call-template name="db2html.autotoc">
      <xsl:with-param name="node" select="/"/>
      <xsl:with-param name="show_info" select="$db.chunk.info_chunk"/>
      <xsl:with-param name="is_info" select="$template = 'info'"/>
      <xsl:with-param name="selected" select="$node"/>
      <xsl:with-param name="divisions" select="/*"/>
      <xsl:with-param name="toc_depth" select="$db.chunk.max_depth + 1"/>
      <xsl:with-param name="titleabbrev" select="true()"/>
    </xsl:call-template>
  </div>
</xsl:template>


<!--**==========================================================================
db2html.division.head.extra
FIXME
:Stub: true

REMARK: Describe this stub template.
-->
<xsl:template name="db2html.division.head.extra"/>


<!--**==========================================================================
db2html.division.top
FIXME
$node: The division element being rendered
$info: The info child element of ${node}
$template: The named template to call to create the page
$depth_of_chunk: The depth of the containing chunk in the document
$prev_id: The id of the previous page
$next_id: The id of the next page
$prev_node: The element of the previous page
$next_node: The element of the next page

REMARK: Describe this template
-->
<xsl:template name="db2html.division.top">
  <xsl:param name="node"/>
  <xsl:param name="info" select="/false"/>
  <xsl:param name="template"/>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="prev_id">
    <xsl:choose>
      <xsl:when test="$depth_of_chunk = 0">
        <xsl:if test="$info and $db.chunk.info_chunk">
          <xsl:value-of select="$db.chunk.info_basename"/>
        </xsl:if>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="db.chunk.chunk-id.axis">
          <xsl:with-param name="node" select="$node"/>
          <xsl:with-param name="axis" select="'previous'"/>
          <xsl:with-param name="depth_in_chunk" select="0"/>
          <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:param>
  <xsl:param name="next_id">
    <xsl:call-template name="db.chunk.chunk-id.axis">
      <xsl:with-param name="node" select="$node"/>
      <xsl:with-param name="axis" select="'next'"/>
      <xsl:with-param name="depth_in_chunk" select="0"/>
      <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="prev_node" select="key('idkey', $prev_id)"/>
  <xsl:param name="next_node" select="key('idkey', $next_id)"/>
  <div class="head">
    <xsl:if test="$db2html.navbar.top">
      <xsl:call-template name="db2html.navbar">
        <xsl:with-param name="node" select="$node"/>
        <xsl:with-param name="prev_id" select="$prev_id"/>
        <xsl:with-param name="next_id" select="$next_id"/>
        <xsl:with-param name="prev_node" select="$prev_node"/>
        <xsl:with-param name="next_node" select="$next_node"/>
      </xsl:call-template>
    </xsl:if>
  </div>
</xsl:template>


<!--FIXME
**==========================================================================
db2html.division.sidebar
FIXME
$node: The division element being rendered
$info: The info child element of ${node}
$template: The named template to call to create the page
$depth_of_chunk: The depth of the containing chunk in the document
$prev_id: The id of the previous page
$next_id: The id of the next page
$prev_node: The element of the previous page
$next_node: The element of the next page

REMARK: Describe this template
-->
<xsl:template name="FIXME.db2html.division.sidebar">
  <xsl:param name="node"/>
  <xsl:param name="info" select="/false"/>
  <xsl:param name="template"/>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="prev_id">
    <xsl:choose>
      <xsl:when test="$depth_of_chunk = 0">
        <xsl:if test="$info and $db.chunk.info_chunk">
          <xsl:value-of select="$db.chunk.info_basename"/>
        </xsl:if>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="db.chunk.chunk-id.axis">
          <xsl:with-param name="node" select="$node"/>
          <xsl:with-param name="axis" select="'previous'"/>
          <xsl:with-param name="depth_in_chunk" select="0"/>
          <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:param>
  <xsl:param name="next_id">
    <xsl:call-template name="db.chunk.chunk-id.axis">
      <xsl:with-param name="node" select="$node"/>
      <xsl:with-param name="axis" select="'next'"/>
      <xsl:with-param name="depth_in_chunk" select="0"/>
      <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="prev_node" select="key('idkey', $prev_id)"/>
  <xsl:param name="next_node" select="key('idkey', $next_id)"/>
  <xsl:if test="$db2html.sidenav">
    <div class="side">
      <xsl:call-template name="db2html.sidenav">
        <xsl:with-param name="node" select="$node"/>
        <xsl:with-param name="template" select="$template"/>
      </xsl:call-template>
    </div>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
db2html.division.bottom
FIXME
$node: The division element being rendered
$info: The info child element of ${node}
$template: The named template to call to create the page
$depth_of_chunk: The depth of the containing chunk in the document
$prev_id: The id of the previous page
$next_id: The id of the next page
$prev_node: The element of the previous page
$next_node: The element of the next page

REMARK: Describe this template
-->
<xsl:template name="db2html.division.bottom">
  <xsl:param name="node"/>
  <xsl:param name="info" select="/false"/>
  <xsl:param name="template"/>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="prev_id">
    <xsl:choose>
      <xsl:when test="$depth_of_chunk = 0">
        <xsl:if test="$info and $db.chunk.info_chunk">
          <xsl:value-of select="$db.chunk.info_basename"/>
        </xsl:if>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="db.chunk.chunk-id.axis">
          <xsl:with-param name="node" select="$node"/>
          <xsl:with-param name="axis" select="'previous'"/>
          <xsl:with-param name="depth_in_chunk" select="0"/>
          <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:param>
  <xsl:param name="next_id">
    <xsl:call-template name="db.chunk.chunk-id.axis">
      <xsl:with-param name="node" select="$node"/>
      <xsl:with-param name="axis" select="'next'"/>
      <xsl:with-param name="depth_in_chunk" select="0"/>
      <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
    </xsl:call-template>
  </xsl:param>
  <xsl:param name="prev_node" select="key('idkey', $prev_id)"/>
  <xsl:param name="next_node" select="key('idkey', $next_id)"/>
  <div class="foot">
    <xsl:if test="$db2html.navbar.bottom">
      <xsl:call-template name="db2html.navbar">
        <xsl:with-param name="node" select="$node"/>
        <xsl:with-param name="prev_id" select="$prev_id"/>
        <xsl:with-param name="next_id" select="$next_id"/>
        <xsl:with-param name="prev_node" select="$prev_node"/>
        <xsl:with-param name="next_node" select="$next_node"/>
      </xsl:call-template>
    </xsl:if>
  </div>
</xsl:template>


<!-- == Matched Templates == -->

<!-- = appendix = -->
<xsl:template match="appendix | db:appendix">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    bibliography | glossary | index      | lot | refentry |
                    sect1        | section  | simplesect | toc |
                    db:bibliography | db:glossary | db:index   |
                    db:refentry     | db:sect1    | db:section |
                    db:simplesect   | db:toc"/>
    <xsl:with-param name="info" select="appendixinfo | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = article = -->
<xsl:template match="article | db:article">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    appendix | bibliography | glossary | index      | lot |
                    refentry | sect1        | section  | simplesect | toc |
                    db:appendix   | db:bibliography | db:glossary | db:index |
                    db:refentry   | db:sect1        | db:section  |
                    db:simplesect | db:toc "/>
    <xsl:with-param name="info" select="articleinfo | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = book = -->
<xsl:template match="book | db:book">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    appendix | article    | bibliography | chapter   |
                    colophon | dedication | glossary     | index     |
                    lot      | part       | preface      | reference |
                    setindex | toc        |
                    db:acknowledgements | db:appendix | db:article   |
                    db:bibliography     | db:chapter  | db:colophon  |
                    db:dedication       | db:glossary | db:index     |
                    db:part             | db:preface  | db:reference |
                    db:toc"/>
    <xsl:with-param name="info" select="bookinfo | db:info"/>
    <!-- Unlike other elements in DocBook, title comes before bookinfo -->
    <xsl:with-param name="title_node"
                    select="(title    | bookinfo/title |
                             db:title | db:info/db:title)[1]"/>
    <xsl:with-param name="subtitle_node"
                    select="(subtitle    | bookinfo/subtitle |
                             db:subtitle | db:info/db:subtitle)[1]"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
    <xsl:with-param name="autotoc_depth" select="2"/>
  </xsl:call-template>
</xsl:template>

<!-- = chapter = -->
<xsl:template match="chapter | db:chapter">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    bibliography | glossary | index      | lot | refentry |
                    sect1        | section  | simplesect | toc |
                    db:bibliography | db:glossary | db:index    |
                    db:refentry     | db:sect1    | db:section  |
                    db:simplesect   | db:toc"/>
    <xsl:with-param name="info" select="chapterinfo | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = dedication = -->
<xsl:template match="dedication | db:dedication">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:choose>
    <xsl:when test="not(title) and not(db:title) and not(db:info/db:title)">
      <xsl:call-template name="db2html.division.div">
        <xsl:with-param name="title_content">
          <xsl:call-template name="l10n.gettext">
            <xsl:with-param name="msgid" select="'Dedication'"/>
          </xsl:call-template>
        </xsl:with-param>
        <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
        <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:otherwise>
      <xsl:call-template name="db2html.division.div">
        <xsl:with-param name="info" select="db:info"/>
        <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
        <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
      </xsl:call-template>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<!-- = glossary = -->
<xsl:template match="glossary | db:glossary">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:choose>
    <xsl:when test="not(title) and not(glossaryinfo/title) and not(db:title) and not(db:info/db:title)">
      <xsl:call-template name="db2html.division.div">
        <xsl:with-param name="entries" select="glossentry | db:glossentry"/>
        <xsl:with-param name="divisions" select="glossdiv | bibliography | db:glossdiv | db:bibliography"/>
        <xsl:with-param name="title_content">
          <xsl:call-template name="l10n.gettext">
            <xsl:with-param name="msgid" select="'Glossary'"/>
          </xsl:call-template>
        </xsl:with-param>
        <xsl:with-param name="info" select="glossaryinfo | db:info"/>
        <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
        <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:otherwise>
      <xsl:call-template name="db2html.division.div">
        <xsl:with-param name="entries" select="glossentry | db:glossentry"/>
        <xsl:with-param name="divisions" select="glossdiv | bibliography | db:glossdiv | db:bibliography"/>
        <xsl:with-param name="info" select="glossaryinfo | db:info"/>
        <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
        <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
      </xsl:call-template>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<!-- = glossdiv = -->
<xsl:template match="glossdiv | db:glossdiv">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="entries" select="glossentry | db:glossentry"/>
    <xsl:with-param name="divisions" select="bibliography | db:bibliography"/>
    <xsl:with-param name="info" select="db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = part = -->
<xsl:template match="part | db:part">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    appendix | article   | bibliography | chapter |
                    glossary | index     | lot          | preface |
                    refentry | reference | toc          |
                    db:appendix  | db:article   | db:bibliography |
                    db:chapter   | db:glossary  | db:index        |
                    db:preface   | db:refentry  | db:reference    |
                    db:toc"/>
    <xsl:with-param name="info" select="partinfo | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = preface = -->
<xsl:template match="preface | db:preface">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    refentry | simplesect | sect1    | section      | toc  |
                    lot      | index      | glossary | bibliography |
                    db:refentry | db:simplesect | db:sect1    | db:section |
                    db:toc      | db:index      | db:glossary |
                    db:bibliography "/>
    <xsl:with-param name="info" select="prefaceinfo | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = qandadiv = -->
<xsl:template match="qandadiv | db:qandadiv">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="info" select="blockinfo | db:info"/>
    <xsl:with-param name="entries" select="qandaentry | db:qandaentry"/>
    <xsl:with-param name="divisions" select="qandadiv | db:qandadiv"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
    <xsl:with-param name="chunk_divisions" select="false()"/>
    <xsl:with-param name="chunk_info" select="false()"/>
    <xsl:with-param name="autotoc_divisions" select="false()"/>
  </xsl:call-template>
</xsl:template>

<!-- = qandaset = -->
<xsl:template match="qandaset | db:qandaset">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="info" select="blockinfo | db:info"/>
    <xsl:with-param name="entries" select="qandaentry | db:qandaentry"/>
    <xsl:with-param name="divisions" select="qandadiv | db:qandadiv"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
    <xsl:with-param name="chunk_divisions" select="false()"/>
    <xsl:with-param name="chunk_info" select="false()"/>
    <xsl:with-param name="autotoc_divisions" select="true()"/>
  </xsl:call-template>
</xsl:template>

<!-- = reference = -->
<xsl:template match="reference | db:reference">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="refentry | db:refentry"/>
    <xsl:with-param name="info" select="referenceinfo | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = sect1 = -->
<xsl:template match="sect1 | db:sect1">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    bibliography | glossary | index      | lot |
                    refentry     | sect2    | simplesect | toc |
                    db:bibliography | db:glossary | db:index      |
                    db:refentry     | db:sect2    | db:simplesect |
                    db:toc "/>
    <xsl:with-param name="info" select="sect1info | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = sect2 = -->
<xsl:template match="sect2 | db:sect2">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    bibliography | glossary | index      | lot |
                    refentry     | sect3    | simplesect | toc |
                    db:bibliography | db:glossary   | db:index | db:refentry |
                    db:sect3        | db:simplesect | db:toc "/>
    <xsl:with-param name="info" select="sect2info | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = sect3 = -->
<xsl:template match="sect3 | db:sect3">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    bibliography | glossary | index      | lot |
                    refentry     | sect4    | simplesect | toc |
                    db:bibliography | db:glossary   | db:index | db:refentry |
                    db:sect4        | db:simplesect | db:toc "/>
    <xsl:with-param name="info" select="sect3info | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = sect4 = -->
<xsl:template match="sect4 | db:sect4">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    bibliography | glossary | index      | lot |
                    refentry     | sect5    | simplesect | toc |
                    db:bibliography | db:glossary   | db:index | db:refentry |
                    db:sect5        | db:simplesect | db:toc "/>
    <xsl:with-param name="info" select="sect4info | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = sect5 = -->
<xsl:template match="sect5 | db:sect5">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    bibliography | glossary   | index | lot |
                    refentry     | simplesect | toc   |
                    db:bibliography | db:glossary   | db:index |
                    db:refentry     | db:simplesect | db:toc   "/>
    <xsl:with-param name="info" select="sect5info | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = section = -->
<xsl:template match="section | db:section">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="divisions" select="
                    bibliography | glossary | index      | lot |
                    refentry     | section  | simplesect | toc |
                    db:bibliography | db:glossary   | db:index | db:refentry |
                    db:section      | db:simplesect | db:toc "/>
    <xsl:with-param name="info" select="sectioninfo | db:info"/>
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

<!-- = simplesect = -->
<xsl:template match="simplesect | db:simplesect">
  <xsl:param name="depth_in_chunk">
    <xsl:call-template name="db.chunk.depth-in-chunk"/>
  </xsl:param>
  <xsl:param name="depth_of_chunk">
    <xsl:call-template name="db.chunk.depth-of-chunk"/>
  </xsl:param>
  <xsl:call-template name="db2html.division.div">
    <xsl:with-param name="depth_in_chunk" select="$depth_in_chunk"/>
    <xsl:with-param name="depth_of_chunk" select="$depth_of_chunk"/>
  </xsl:call-template>
</xsl:template>

</xsl:stylesheet>
