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
                xmlns:ui="http://projectmallard.org/experimental/ui/"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="mal ui"
                version="1.0">

<!--!!==========================================================================
Mallard to HTML - UI Extension
Support for Mallard UI extension elements.

This stylesheet contains templates to support features from the Mallard UI
extension.
-->


<!--**==========================================================================
mal2html.ui.expander.data
Output data for an expander.
:Revision:version="1.0" date="2011-06-14" status="final"
$node: The source element to output data for.
$expander: Whether ${node} is actually an expander.

This template outputs an HTML #{div} element with the #{class} attribute set to
#{"yelp-data yelp-data-ui-expander"}. All #{yelp-data} elements are hidden by
the CSS. The div contains information about text directionality, the default
expanded state, and optionally additional titles for the expanded and collapsed
states.

The expander information is only output if the ${expander} parameter is #{true}.
This parameter can be calculated automatically, but it will give false negatives
for blocks that produce automatic titles.
-->
<xsl:template name="mal2html.ui.expander.data">
  <xsl:param name="node" select="."/>
  <xsl:param name="expander" select="$node/mal:title and
                                     ($node/@ui:expanded or $node/self::ui:expander)"/>
  <xsl:if test="$expander">
    <xsl:variable name="title_e" select="$node/mal:info/mal:title[@type = 'ui:expanded'][1]"/>
    <xsl:variable name="title_c" select="$node/mal:info/mal:title[@type = 'ui:collapsed'][1]"/>
    <div class="yelp-data yelp-data-ui-expander">
      <xsl:attribute name="dir">
        <xsl:call-template name="l10n.direction"/>
      </xsl:attribute>
      <xsl:attribute name="data-yelp-expanded">
        <xsl:choose>
          <xsl:when test="$node/self::ui:expander/@expanded = 'no'">
            <xsl:text>no</xsl:text>
          </xsl:when>
          <xsl:when test="$node/@ui:expanded = 'no'">
            <xsl:text>no</xsl:text>
          </xsl:when>
          <xsl:otherwise>
            <xsl:text>yes</xsl:text>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:attribute>
      <xsl:if test="$title_e">
        <div class="yelp-title-expanded">
          <xsl:apply-templates mode="mal2html.inline.mode" select="$title_e/node()"/>
        </div>
      </xsl:if>
      <xsl:if test="$title_c">
        <div class="yelp-title-collapsed">
          <xsl:apply-templates mode="mal2html.inline.mode" select="$title_c/node()"/>
        </div>
      </xsl:if>
    </div>
  </xsl:if>
</xsl:template>

</xsl:stylesheet>
