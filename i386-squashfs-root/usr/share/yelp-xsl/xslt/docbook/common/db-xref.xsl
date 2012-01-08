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
                xmlns:xl="http://www.w3.org/1999/xlink"
                xmlns:msg="http://projects.gnome.org/yelp/gettext/"
                xmlns:set="http://exslt.org/sets"
                exclude-result-prefixes="db xl msg set"
                version="1.0">

<!--!!==========================================================================
DocBook Links
:Requires: db-chunk db-title gettext
-->


<!--**==========================================================================
db.ulink.tooltip
Generates the tooltip for an external link
$node: The element to generate a tooltip for
$url: The URL of the link, usually from the #{url} attribute
-->
<xsl:template name="db.ulink.tooltip">
  <xsl:param name="node" select="."/>
  <xsl:param name="url" select="$node/@url | $node/@xl:href"/>
  <xsl:choose>
    <xsl:when test="starts-with($url, 'mailto:')">
      <xsl:variable name="addy" select="substring-after($url, 'mailto:')"/>
      <xsl:call-template name="l10n.gettext">
        <xsl:with-param name="msgid" select="'email.tooltip'"/>
        <xsl:with-param name="string" select="$addy"/>
        <xsl:with-param name="format" select="true()"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:otherwise>
      <xsl:value-of select="normalize-space($url)"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>


<!--**==========================================================================
db.xref.content
Generates the content of a cross reference
$linkend: The id of the linked-to element, usually from the #{linkend} attribute
$target: The linked-to element
$xrefstyle: The cross reference style, usually from the #{xrefstyle} attribute

REMARK: The xrefstyle/role stuff needs to be documented
-->
<xsl:template name="db.xref.content">
  <xsl:param name="linkend" select="@linkend"/>
  <xsl:param name="target" select="key('idkey', $linkend)"/>
  <xsl:param name="xrefstyle" select="@xrefstyle"/>
  <xsl:choose>
    <xsl:when test="$xrefstyle = 'role:title'">
      <xsl:call-template name="db.title">
        <xsl:with-param name="node" select="$target"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:when test="$xrefstyle = 'role:titleabbrev'">
      <xsl:call-template name="db.titleabbrev">
        <xsl:with-param name="node" select="$target"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:when test="$xrefstyle = 'role:subtitle'">
      <xsl:call-template name="db.subtitle">
        <xsl:with-param name="node" select="$target"/>
      </xsl:call-template>
    </xsl:when>
    <xsl:when test="$target/@xreflabel">
      <xsl:value-of select="$target/@xreflabel"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:call-template name="db.title">
        <xsl:with-param name="node" select="$target"/>
      </xsl:call-template>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>



<!--**==========================================================================
db.xref.target
Generates the target identifier of a cross reference
$linkend: The id of the linked-to element, usually from the #{linkend} attribute
$target: The linked-to element
$is_chunk: Whether ${target} is known to be a chunked element

REMARK: Talk about how this works with chunking
-->
<xsl:template name="db.xref.target">
  <xsl:param name="linkend" select="@linkend"/>
  <xsl:param name="target" select="key('idkey', $linkend)"/>
  <xsl:param name="is_chunk" select="false()"/>
  <xsl:choose>
    <xsl:when test="$linkend = $db.chunk.info_basename">
      <xsl:value-of
       select="concat($db.chunk.info_basename, $db.chunk.extension)"/>
    </xsl:when>
    <xsl:when test="set:has-same-node($target, /*)">
      <xsl:value-of select="concat($db.chunk.basename, $db.chunk.extension)"/>
    </xsl:when>
    <xsl:when test="$is_chunk">
      <xsl:value-of select="concat($linkend, $db.chunk.extension)"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:variable name="target_chunk_id">
        <xsl:call-template name="db.chunk.chunk-id">
          <xsl:with-param name="node" select="$target"/>
        </xsl:call-template>
      </xsl:variable>
      <xsl:value-of select="concat($target_chunk_id, $db.chunk.extension)"/>
      <xsl:if test="string($linkend) != '' and string($target_chunk_id) != string($linkend)">
        <xsl:value-of select="concat('#', $linkend)"/>
      </xsl:if>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>


<!--**==========================================================================
db.xref.tooltip
Generates the tooltip for a cross reference
$linkend: The id of the linked-to element, usually from the #{linkend} attribute
$target: The linked-to element

REMARK: Document this
-->
<xsl:template name="db.xref.tooltip">
  <xsl:param name="linkend" select="@linkend"/>
  <xsl:param name="target" select="key('idkey', $linkend)"/>
  <xsl:apply-templates mode="db.xref.tooltip.mode" select="$target"/>
</xsl:template>


<!--%%==========================================================================
db.xref.tooltip.mode
FIXME

REMARK: Document this
-->
<xsl:template mode="db.xref.tooltip.mode" match="*">
  <xsl:call-template name="db.title">
    <xsl:with-param name="node" select="."/>
  </xsl:call-template>
</xsl:template>

<!-- = db.xref.tooltip.mode % biblioentry | bibliomixed = -->
<xsl:template mode="db.xref.tooltip.mode" match="biblioentry    | bibliomixed    |
                                                 db:biblioentry | db:bibliomixed ">
  <xsl:call-template name="l10n.gettext">
    <xsl:with-param name="msgid" select="'biblioentry.tooltip'"/>
    <xsl:with-param name="node" select="."/>
    <xsl:with-param name="format" select="true()"/>
  </xsl:call-template>
</xsl:template>

<!-- = db.xref.tooltip.mode % glossentry = -->
<xsl:template mode="db.xref.tooltip.mode" match="glossentry | db:glossentry">
  <xsl:call-template name="l10n.gettext">
    <xsl:with-param name="msgid" select="'glossentry.tooltip'"/>
    <xsl:with-param name="node" select="."/>
    <xsl:with-param name="format" select="true()"/>
  </xsl:call-template>
</xsl:template>

<!--#% l10n.format.mode -->
<xsl:template mode="l10n.format.mode" match="msg:glossterm">
  <xsl:param name="node"/>
  <xsl:apply-templates select="$node/glossterm/node() | $node/db:glossterm/node()"/>
</xsl:template>

</xsl:stylesheet>
