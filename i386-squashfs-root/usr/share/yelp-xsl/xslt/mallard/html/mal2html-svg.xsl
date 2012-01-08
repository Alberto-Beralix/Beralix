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
                xmlns:mal="http://projectmallard.org/1.0/"
                xmlns:svg="http://www.w3.org/2000/svg"
                xmlns:xlink="http://www.w3.org/1999/xlink"
                xmlns:exsl="http://exslt.org/common"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="mal svg xlink"
                extension-element-prefixes="exsl"
                version="1.0">

<!--!!==========================================================================
Mallard to HTML - SVG
Handle embedded SVG.
:Revision: version="1.0" date="2010-06-04" status="final"

This stylesheet matches embedded SVG in %{mal2html.block.mode} and processes it
in %{mal2html.svg.mode}.
-->

<!--%%==========================================================================
mal2html.svg.mode
Output SVG and handle Mallard extension.
:Revision: version="1.0" date="2010-06-04" status="final"

This mode is used for processing SVG embedded into Mallard documents. For most
types of SVG content, it simply copies the input directly. It does check for
certain Mallard extensions, for example to use the Mallard linking mechanism.
-->
<xsl:template mode="mal2html.svg.mode" match="svg:*">
  <xsl:choose>
    <xsl:when test="@mal:xref">
      <xsl:variable name="target">
        <xsl:call-template name="mal.link.target">
          <xsl:with-param name="node" select="."/>
          <xsl:with-param name="xref" select="@mal:xref"/>
        </xsl:call-template>
      </xsl:variable>
      <xsl:variable name="title">
        <xsl:call-template name="mal.link.content">
          <xsl:with-param name="xref" select="@mal:xref"/>
          <xsl:with-param name="role" select="'text'"/>
        </xsl:call-template>
      </xsl:variable>
      <svg:a xlink:href="{$target}" xlink:show="replace"
             xlink:title="{$title}" target="_top">
        <xsl:copy>
          <xsl:for-each select="@*">
            <xsl:copy/>
          </xsl:for-each>
          <xsl:apply-templates mode="mal2html.svg.mode" select="node()"/>
        </xsl:copy>
      </svg:a>
    </xsl:when>
    <xsl:otherwise>
      <xsl:copy>
        <xsl:for-each select="@*">
          <xsl:copy/>
        </xsl:for-each>
        <xsl:apply-templates mode="mal2html.svg.mode" select="node()"/>
      </xsl:copy>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template mode="mal2html.svg.mode" match="text()">
  <xsl:copy-of select="."/>
</xsl:template>

<xsl:template mode="mal2html.block.mode" match="svg:svg">
  <xsl:variable name="if"><xsl:call-template name="mal.if.test"/></xsl:variable><xsl:if test="$if = 'true'">
  <xsl:variable name="id">
    <xsl:choose>
      <xsl:when test="@xml:id">
        <xsl:value-of select="@xml:id"/>
      </xsl:when>
      <xsl:when test="@id">
        <xsl:value-of select="@id"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="generate-id(.)"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <xsl:choose>
    <xsl:when test="$html.xhtml">
      <div class="svg">
        <xsl:apply-templates mode="mal2html.svg.mode" select="."/>
      </div>
    </xsl:when>
    <xsl:otherwise>
      <div class="svg">
        <object data="{$id}.svg" type="image/svg+xml">
          <xsl:copy-of select="@width"/>
          <xsl:copy-of select="@height"/>
        </object>
      </div>
      <exsl:document href="{$id}.svg">
        <xsl:apply-templates mode="mal2html.svg.mode" select="."/>
      </exsl:document>
    </xsl:otherwise>
  </xsl:choose>
</xsl:if>
</xsl:template>

</xsl:stylesheet>
